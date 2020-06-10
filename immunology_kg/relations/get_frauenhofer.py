#-*- coding: utf-8 -*-
"""
Download the Frauenhofer Knowledge Graph. Extract data from the graph
covering sentences, entity relations, and paper citation metadata.
"""

import re
import json
import requests

import pybel
import pandas as pd

from utils import setup_logger

logger = setup_logger(name="get-frauenhofer")

FRAUENHOFER_CSV = "covid19_frauenhofer_kg.csv"
FRAUENHOFER_JSON = "covid19_frauenhofer_kg.json"
#FRAUENHOFER_URL = 'https://github.com/covid19kg/covid19kg/raw/master/covid19kg/_cache.bel.nodelink.json'
FRAUENHOFER_URL = 'https://github.com/CoronaWhy/bel4corona/raw/master/data/covid19kg/covid19-fraunhofer-grounded.bel.nodelink.json'

def download_frauenhofer():
    res = requests.get(FRAUENHOFER_URL)
    res_json = res.json()
    with open(FRAUENHOFER_JSON, 'w', encoding='utf-8') as outfile:
        json.dump(res_json, outfile)
    graph = pybel.from_nodelink(res_json)
    #col0: subject (type e.g. chemical, genes, proteins, etc. and entity)
    #col1: predicate (relationship) 
    #col2: object (type e.g. chemical, genes, proteins, etc. and entity)
    #col4: raw annotation data
    pybel.to_csv(graph, FRAUENHOFER_CSV) #pybel's csv sep='\t'

def load_frauenhofer_json():
    with open(FRAUENHOFER_JSON, 'r', encoding='utf-8') as infile:
        data = json.load(infile)
    return data 

def get_entity_names(node):
    """
    Recursively walk nodes to get all entity name strings 
    in the graph and their concept.
    """
    if "concept" in node:
        names = {}
        names[node["concept"]["name"]] = node["concept"]
        return names
    elif "members" in node:
        names = {}
        for item in node["members"]:
            names.update(get_entity_names(item))
        return names
    elif "reactants" in node:
        names = {}
        for item in node["reactants"]:
            names.update(get_entity_names(item))
        return names
    else:
        return {}

def get_entity_names_from_graph(data):
    """
    Get all the entity name strings from the graph and their concept.
    """
    names = {}
    skipped = 0
    for i in range(len(data["nodes"])):
        result = get_entity_names(data["nodes"][i])
        if not result:
            skipped += 1
        names.update(result)
    logger.info("Skipped nodes without names: {} / {} ({:.1f}%) entries".format(
        skipped, i, (skipped / i)*100))
    return names

def collect_sentences(data):
    """
    Read the PyBel graph-as-dict structure of the Frauenhofer dataset
    and extract all the necessary data to construct a list of lists
    consisting of the [sentence, source, relation, target, metadata].

    NOTE: this is distinct from the Frauenhofer pybel csv file, 
    in that the source and target entities are simple names here, 
    without all the extra graph structure annotations. 
    """
    entries = []
    fail = 0
    pmc_citations = 0
    doi_citations = 0
    for i in range(len(data["links"])):
        link = data['links'][i]
        src_idx = link['source']
        tgt_idx = link['target']
        source = data['nodes'][src_idx]
        target = data['nodes'][tgt_idx]
        relation = link['relation']
        src_term = get_entity_names(source)
        tgt_term = get_entity_names(target)
        pmc_id = None
        doi_id = None

        if 'citation' in link:
            citation = link['citation']
            if 'db' in citation and citation['db'] == 'PubMed' and 'db_id' in citation:
                pmc_id = citation['db_id']
                pmc_citations += 1
            if 'db' in citation and citation['db'] == 'DOI' and 'db_id' in citation:
                doi_id = citation['db_id']
                doi_citations += 1

        if 'evidence' in link:
            sentence = link['evidence']
        else:
            #use an empty string instead of None so that when we feed the whole
            #list of sentences to Spacy later we don't run into type problems
            sentence = ''
            fail += 1

        entries.append([
            sentence, 
            src_term, 
            relation, 
            tgt_term, 
            link, 
            pmc_id, 
            doi_id
        ])
        
    missing_citations = i - (pmc_citations + doi_citations)
    logger.info("Sentences not available for {} / {} ({:.2f}%) entries".format(
        fail, i, (fail / i)*100))
    logger.info("Citations not available for {} / {} ({:.2f}%) entries".format(
        missing_citations, 
        i, 
        (missing_citations / i) * 100
    ))
    return entries

def get_cited_sentences(data):
    entries = collect_sentences(data)
    df = pd.DataFrame(
        entries,
        columns=['sentence', 'source', 'relation', 'target', 'link', 'pmc_id', 'doi_id']
    )
    cite_df = df.dropna(subset=['pmc_id', 'doi_id'], how="all")
    cite_df.to_csv('covid19_frauenhofer_annotations.csv')
    return cite_df

def main():
    download_frauenhofer()
    data = load_frauenhofer_json()
    cite_df = get_cited_sentences(data)
    logger.info("Sentence annotations with citations: {} / {} ({:.2f}%)".format(
        len(cite_df), len(cite_df), (len(cite_df) / len(cite_df))*100))
    logger.info("Sample:")
    logger.info(cite_df.head())
    logger.info(cite_df.tail())
    return cite_df


if __name__ == '__main__':
    main()





