'''A module to create Tensorflow TFrecord files for Vica.

TFrecords files are a binary serialized format that contains examples for
    machine learning and classification by Tensorflow
    https://www.tensorflow.org/api_docs/python/tf/data/TFRecordDataset.
    The format is specified
    in Protobuff format  https://developers.google.com/protocol-buffers/.

'''

import subprocess
import os
import logging
import yaml
import json

import ete3
import tensorflow as tf
import numpy as np

import vica

with open(vica.CONFIG_PATH) as cf:
    config = yaml.safe_load(cf)

def external_sort(infile, outfile, sep, key=1):
    """Externally sort and make unique csv files using built-in GNU Coreutils.

    Args:
        infile (str): the csv file to sort
        outfile (str): the location to write the sorted csv file
        sep (str): the separator for the columns
        key (int): the column containing the id to sort on

    Returns:
        (str): the path to the outfile created

    References:
        GNU Coreutils: https://www.gnu.org/software/coreutils/coreutils.html

    """
    try:
        os.environ["LC_ALL"]="C"
        sortoptions = ['sort', '-t', sep, '-k', '1b,'+ str(key), '-s','-u', '-o', outfile,  infile ]
        subprocess.run(sortoptions, check=True,)
        return outfile
    except:
        logging.exception("Input files could not be sorted")

def join(kmerfile, codonfile, dtemp):
    """Externally join with built-in GNU Coreutils in the order
        label, kmers, codons ,minhash

    Args:
        kmerfile (str): Kmer csv file
        codonfile (str): Codon csv file
        dtemp (str): the path to a temporary directory

    Returns:
        (str) the path of the merged file created

    References:
        GNU Coreutils: https://www.gnu.org/software/coreutils/coreutils.html

    """
    os.environ["LC_ALL"]="C"
    mergefile = os.path.join(dtemp, "mergefile.csv")
    try:
        with open(mergefile, 'w') as mf:
            options = ['join', '-t', ',', '-1', '1', '-2', '1', kmerfile, codonfile]
            subprocess.run(options,  check=True, stdout=mf)
        return mergefile
    except RuntimeError:
        logging.exception("Could not merge csv files using unix join command")


def create_class2labels(classdict):
    ncbi = ete3.NCBITaxa()
    class2labels = {}
    for i, val in enumerate(classdict.keys()):
        taxa = ncbi.get_taxid_translator([val])
        class2labels[val] = {"name": taxa[val], "class": i}
    logging.info("Class labels are %s", class2labels)
    return(class2labels)




def _label_lookup(class2labels, seqid, ncbi):
    try:
        taxid = seqid.split("|")[1]
        lineage = ncbi.get_lineage(taxid)
        classtaxid = list(set(class2labels.keys()).intersection(lineage))
        assert len(classtaxid) == 1
        return class2labels[classtaxid[0]]["class"]
    except:
        logging.info("Could not determine the class for taxid %s, randomly assigned class " % str(taxid))
        return random.randint(0, len(classdict)-1)



def _data_to_tfrecords(kmerfile, codonfile, minhashfile, mergefile, hmmerfile, tfrecordfile):
    """Convert csv and json data files of features created by Vica into a TFRecords file.

    Args:
        kmerfile (str): a csv file containing ilr transformed kmer count data
        codonfile (str): a csv file containing ilr transformed codon count data
        minhashfile (str): a csv file containing scores for selected
            phylogenetic levels generated by the vica.minhash module
        mergefile (str): a merged CSV file created by `vica.tfrecord_maker.join`
        tfrecordfile (str): the location to write the TTRecords files


    Returns:
        None

    """
    writer = tf.python_io.TFRecordWriter(tfrecordfile)
    kend = config['train_eval']['kmerlength']
    cend = kend + config['train_eval']['codonlength']
    class2labels = create_class2labels(config["split_shred"]["classes"])
    ncbi = ete3.NCBITaxa()
    with open(hmmerfile, 'r') as hmmerdata:
        hmmerdatadict = json.load(hmmerdata)
    with open(minhashfile, 'r') as minhashdata:
        minhashdatadict = json.load(minhashdata)
    with open(mergefile, 'r') as mergedata:
        for i, lstring in enumerate(mergedata, 1):
            line = lstring.strip().split(",")
            seqid = line[0]
            kdat = np.array(line[1:kend], dtype='float32')
            cdat = np.array(line[kend:cend], dtype='float32')
            if seqid in minhashdatadict:
                mhlist = [tf.compat.as_bytes(str(minhashdatadict[seqid]))]
            else:
                mhlist = [tf.compat.as_bytes("nohits")]
            label = _label_lookup(class2labels, seqid, ncbi)
            if seqid in hmmerdatadict["data"]:
                hmmlist = [tf.compat.as_bytes(x) for x in hmmerdatadict["data"][seqid]]
            else:
                hmmlist = [tf.compat.as_bytes("nohits")]

            example = tf.train.Example(features=tf.train.Features(feature={
                "id":
                    tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(seqid)])),
                "kmer":
                    tf.train.Feature(float_list=tf.train.FloatList(value=kdat)),
                "codon":
                    tf.train.Feature(float_list=tf.train.FloatList(value=cdat)),
                "minhash":
                    tf.train.Feature(bytes_list=tf.train.BytesList(value=mhlist)),
                "hmmer":
                    tf.train.Feature(bytes_list=tf.train.BytesList(value=hmmlist)),
                "label":
                    tf.train.Feature(int64_list=tf.train.Int64List(value=[label]))
                }))
            writer.write(example.SerializeToString())
    writer.close()
    logging.info("Successfully converted {} records to to TFrecord format".format(i))


def convert_to_tfrecords(dtemp, kmerfile, codonfile, minhashfile, hmmerfile,
                         tfrecordfile, sort=False):
    """Combines features files created by Vica into a TFRecords file.

    Args:
        dtemp (str): a temporary directory path
        kmerfile (str): a csv file containing ilr transformed kmer count data
        codonfile (str): a csv file containing ilr transformed codon count data
        minhashfile (str): a csv file containing scores for selected
            phylogenetic levels generated by the vica.minhash module
        tfrecordfile (str): the location to write the TTRecords files
        label (int): an integer label to add to each TFRecords example. Use
            one sequential integer for each class.
        sort (bool): Whether to externally sort the files prior to attempting to
            merge them. Doing so allows missing data lines in files to be
            fixed. Requires GNU Utils sort, which is standard on POSIX systems.

    Returns:
        None

    """
    if sort:
        ksorted = os.path.join(dtemp, "kmer_sorted.csv")
        csorted = os.path.join(dtemp, "codon_sorted.csv")
        mergefile = os.path.join(dtemp, "mergefile.csv")
        external_sort(infile=kmerfile, outfile=ksorted, sep=",")
        external_sort(infile=codonfile, outfile=csorted, sep=",")
    else:
        ksorted = kmerfile
        csorted = codonfile
    mergefile = join(kmerfile=ksorted, codonfile=csorted, dtemp=dtemp)
    _data_to_tfrecords(kmerfile=ksorted, codonfile=csorted, minhashfile=minhashfile,
                       mergefile=mergefile, hmmerfile=hmmerfile,
                       tfrecordfile=tfrecordfile)
