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

import tensorflow as tf
import numpy as np


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
        sortoptions = ['sort', '-t', sep, '-k', str(key), '-s','-u', '-o', outfile,  infile ]
        subprocess.run(sortoptions, check=True,)
        return outfile
    except:
        logging.exception("Input files could not be sorterd")

def join(kmerfile, codonfile, minhashfile, dtemp):
    """Externally join with built-in GNU Coreutils in the order
        label, kmers, codons ,minhash

    Args:
        kmerfile (str): Kmer csv file
        codonfile (str): Codon csv file
        minhashfile (str): Minhash csv file
        dtemp (str): the path to a temporary directory

    Returns:
        (str) the path of the merged file created

    References:
        GNU Coreutils: https://www.gnu.org/software/coreutils/coreutils.html

    """
    kcfile= os.path.join(dtemp, "kcfile.csv")
    mergefile = os.path.join(dtemp, "mergefile.csv")
    try:
        with open(kcfile, 'w') as kcf:
            options = ['join', '-t', ',', '-1', '1', '-2', '1', kmerfile, codonfile]
            subprocess.run(options,  check=True, stdout=kcf)
        with open(mergefile, "w") as  mf:
            options2 = ['join', '-t', ',', '-1', '1', '-2', '1', kcfile, minhashfile]
            subprocess.run(options2,  check=True, stdout=mf)
        os.remove(kcfile)
        return mergefile
    except RuntimeError:
        logging.exception("Could not merge csv files using unix join command")

def count_features(**kwargs):
    """Given key-value pairs of fileypes: file locations return a dictionary
        of filetypes: feature lengths.

        Args:
            **bar (**kwargs): Key-Value pairs of file_type: file_path

        Returns:
            (dict): A dict with {file_type (str): feature_length (int)}

    """
    featuredict ={}
    for key, val in kwargs.items():
        with open(val, 'r') as f:
            features = len(f.readline().strip().split(",")) - 1
        featuredict[key] = features
    return featuredict


def _csv_to_tfrecords(kmerfile, codonfile, minhashfile, mergefile, tfrecordfile, label):
    """Convert csv files of features created by Vica into a TFRecords file.

    Args:
        kmerfile (str): a csv file contianing ilr transformed kmer count data
        codonfile (str): a csv file contianing ilr transformed codon count data
        minhashfile (str): a csv file containing scores for selected
            phylogenetic levels generated by the vica.minhash module
        mergefile (str): a merged CSV file created by `vica.tfrecord_maker.join`
        tfrecordfile (str): the location to write the TTRecords files
        label (int): an integer label to add to each TFRecords example. Use
            one sequential integer for each class.

    Returns:
        None

    """
    writer = tf.python_io.TFRecordWriter(tfrecordfile)
    features = count_features(kmers=kmerfile,codons=codonfile,minhash=minhashfile)
    kstart = 1
    kend = features['kmers'] + 1
    cend = kend + features['codons']
    i = 0
    with open(mergefile, 'r') as mergedata:
        for i, lstring in enumerate(mergedata, 1):
            line = lstring.strip().split(",")
            lab = line[0]
            kdat = np.array(line[kstart:kend], dtype='float32')
            cdat = np.array(line[kend:cend], dtype='float32')
            mdat = np.array(line[cend:], dtype='float32')
            example = tf.train.Example(features=tf.train.Features(feature={
                "id":
                    tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.compat.as_bytes(lab)])),
                "label":
                    tf.train.Feature(int64_list=tf.train.Int64List(value=[int(label)])),
                "kmer":
                    tf.train.Feature(float_list=tf.train.FloatList(value=kdat)),
                "codon":
                    tf.train.Feature(float_list=tf.train.FloatList(value=cdat)),
                "minhash":
                    tf.train.Feature(float_list=tf.train.FloatList(value=mdat))
                }))
            writer.write(example.SerializeToString())
    writer.close()
    logging.info("Successfully converted {} records to to TFrecord format".format(i))


def convert_to_tfrecords(dtemp, kmerfile, codonfile, minhashfile,
                         tfrecordfile, label, sort=False):
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
        sort (bool): Whether to externally sot the files brior to attempting to
            merge them. Doing so allows missing data lines in files to be
            fixed. Requires GNU Utils sort, which is standard on POSIX systems.

    Returns:
        None

    """
    if sort:
        ksorted = os.path.join(dtemp, "kmer_sorted.csv")
        csorted = os.path.join(dtemp, "codon_sorted.csv")
        msorted = os.path.join(dtemp, "minhash_sorted.csv")
        mergefile = os.path.join(dtemp, "mergefile.csv")
        external_sort(infile=kmerfile, outfile=ksorted, sep=",")
        external_sort(infile=codonfile, outfile=csorted, sep=",")
        external_sort(infile=minhashfile, outfile=msorted, sep=",")
    else:
        ksorted = kmerfile
        csorted = codonfile
        msorted = minhashfile
    mergefile = join(kmerfile=ksorted, codonfile=csorted, minhashfile=msorted, dtemp=dtemp)
    _csv_to_tfrecords(kmerfile=ksorted, codonfile=csorted, minhashfile=msorted,mergefile=mergefile,
                     tfrecordfile=tfrecordfile, label=label)
