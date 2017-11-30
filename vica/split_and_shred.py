#!/usr/bin/env python3
"""split_and_shred.py"""

import pyfaidx
import ete3
import pandas
import logging
import numpy
import subprocess
import os

#load fasta records and create index
def _read_data(file):
    """read a fasta or bgzf fasta and optionally an equivelantly named faidx and return a pyfaidx handle"""
    seqobj = pyfaidx.Fasta(file, read_ahead=10000)#, read_long_names=True)
    return seqobj


def _shuffle_keys(ddict):
    """take the pyfaidx file and return a suffled list of the keys"""
    keylist = []
    for key in ddict.keys():
        keylist.append(key)
    kls = random.shuffle(keylist)
    return keylist

# def _get_taxonomy(minlevel, maxlevel, treefile, infile):
#     """takes a bbtools formatted sequence fasta file and retuns a list containing the lineage at the min and max levels requested"""
#     options = ["taxonomy.sh",
#                "tree=" + treefile,
#                "minlevel=" + minlevel,
#                "maxlevel=" + minlevel,
#                "in=" + infile]
#     sendsketchout = subprocess.run(options, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     logging.info(sendsketchout.stderr.decode('utf-8'))
#     return sendsketchout.stdout.decode('utf-8').splitlines()
#
# def _parse_bbtools_taxonomy(taxlist):
#     newdict = {}
#     for item in taxlist:
#         if item == '':
#             taxid = None
#         elif item.startswith("tid"):
#             readid = item.strip().split(" ")[0]
#             taxid = readid.split("|")[1]
#         else:
#             ll = item.strip().split('\t')
#             newdict[taxid] = {"level":ll[0], "level_taxid"[ll[1], "levelname":ll[2]}
#             next
#     labels = ["seqeuence_taxid","level","level_taxid","levelname"]
#     df = pandas.DataFrame.from_dict(newlist, columns=labels)
#     # by default pandas drops all entries after the first
#     df = df.drop_duplicates("seqeuence_taxid")
#     return df



def _profile_sequences(seqobj, ncbiobj, splitlevel, classes):
    """collect data on all sequences in the reference db"""
    taxlevels = ['species', 'genus', 'family', 'order','class', 'phylum', 'kingdom', ]
    datadict = {}
    for key in seqobj.keys():
        try:
            rec = key.strip().split("|")
            tid = rec[1]
            accession = rec[2]
            length = len(seqobj[key])
            revlinlist = ncbiobj.get_lineage(tid)[::-1]
            rankdict = ncbiobj.get_rank(revlinlist)
            sltaxon = None
            cltaxon = None
            for item in revlinlist:
                if rankdict[item] == splitlevel:
                    sltaxon = item
                if item in classes:
                    cltaxon = item
            datadict[key] = [tid, sltaxon, cltaxon, length]
        except Exception:
            logging.exception("An error occured while profiling the sequence {} in the reference database. Coninuing with the next sequence.".format(str(key)))
            pass
    df = pandas.DataFrame.from_dict(datadict, orient="index")
    df.columns = ["taxid", "taxlevelid", "classid", "length"]
    return df

def _split_levels(testfrac, df, classes):
    """Split the taxa at the selected level into test and train"""
    cd = {}
    for taxid in classes:
         dff = df[df.classid==taxid]
         classids =set(dff['taxlevelid'])
         clength = len(classids)
         test = round(clength*testfrac)
         testids = set(numpy.random.choice(a=list(classids), size = test, replace=False))
         trainids = set(classids) - testids
         cd[taxid]={'test':testids,'train': trainids, 'total':clength}
    return(cd)

def writeseq(record, pos, length, handle):
    """writes a fasta sequence to a file, adding position information to the id"""
    seqlist = []
    label = (">" + record.name + "|pos|" + str(pos) + ".." + str(pos + length) + "\n")
    end = pos + length
    result = record[pos:end].seq
    seqlist = [result[n:n + 60] +'\n' for n in range(0, len(result), 60)]
    handle.write(label)
    handle.writelines(seqlist)



# >>> Left off here<<<
def _select_contigs(n_per_class, cd, outdir, length, df, seqobj):
    """select contigs for testing and training for each classifier class with
       even sampling in each taxon at the selected taxonomic level.
       Writes to the output directory."""

    def process_examples(exampletype):
        tot_recs = 0
        for taxid in cd:
            recs_written = 0
            #calcualte the samples required to get an even sampling from each taxa level
            rec_per_level = round(n_per_class/cd[taxid]['total'])
            # select those taxa from the dataframe
            testdf = df[df.taxlevelid.isin(cd[taxid][exampletype])]
            # calculate number of samples per taxa level
            print(testdf)
            testsize = round(n_per_class * len(cd[taxid][exampletype])/cd[taxid]['total'])
            print(type(testsize))
            # select the examples contigs based in their fraction of genomic length in the taxa level
            testvect = numpy.random.choice(a= testdf.index.values, p=testdf["length"]/sum(testdf["length"]),size=testsize)
            #For each contig select a fragment of desired length
            outfile = os.path.join(outdir, exampletype, str(taxid) + ".fasta")
            with open(outfile, 'w') as outhandle:
                for name in testvect:
                    seq_length = len(seqobj[name])
                    # verify the contig is long enough
                    if seq_length > length:
                        # select a random starting point
                        pos = numpy.random.choice(seq_length - length)
                        # calculate an end position
                        endpos = pos + length
                        # verif y the reads is less than 10% N's
                        if seqobj[name][pos: endpos].seq.count("N")/length < 0.1:
                            writeseq(seqobj[name], pos, length, outhandle)
                            recs_written += 1
                            tot_recs += 0
            logging.info("Wrote {} fragmented sequences to the {} directory in the class {}".format(recs_written, exampletype, taxid))
        return tot_recs

    tot_written = 0
    # create output directory
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    # make output directories
    testdir = os.path.join(outdir,"test")
    if not os.path.exists(testdir):
        os.mkdir(testdir)
    traindir = os.path.join(outdir,"train")
    if not os.path.exists(testdir):
        os.mkdir(traindir)
    # for each test and train:
    testcount = process_examples('test')
    traincount = process_examples('train')
    logging.info("Wrote a total of {} testing and {} training fragmented sequences.".format(testcount, traincount))


def shred_all(fastafile, outdir, length=5000, n_per_class=100000, testfrac =0.1, splitlevel="family",
              classes={2: "Bacteria",
                       2157: "Archaea",
                       2759: "Eukaryota",
                       10239: "Viruses"}):
    """shred all sequences to the desired length"""
    # Read data as pyfaidx object
    seqobj = _read_data(fastafile)
    ncbi = ete3.NCBITaxa()
    df = _profile_sequences(seqobj, ncbi, splitlevel, classes)
    cd = _split_levels(testfrac=testfrac, df=df, classes=classes)
    _select_contigs(n_per_class=n_per_class, cd=cd, outdir=outdir,length=length,df=df, seqobj=seqobj)