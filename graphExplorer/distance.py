from gargantext.util.db import session

from collections import defaultdict
from operator import itemgetter
from django.db import connection, transaction

import math
from math import log,sqrt

import numpy as np
import pandas as pd

from copy import copy
import networkx as nx
from networkx.readwrite import json_graph

from graphExplorer.louvain import best_partition, generate_dendogram, partition_at_level

from sqlalchemy.orm import aliased


def do_distance(cooc_id, field1=None, field2=None, isMonopartite=True, distance='conditional'):
    '''
    do_distance :: Int -> (Graph, Partition, {ids}, {weight})
    '''
    
    # implicit global session

    authorized = ['conditional', 'distributional', 'cosine']
    if distance not in authorized:
        distance = 'conditional'

    matrix = defaultdict(lambda : defaultdict(float))
    ids    = defaultdict(lambda : defaultdict(int))
    labels = dict()
    weight = dict()

    Cooc = aliased(NodeNgramNgram)

    query = session.query(Cooc).filter(Cooc.node_id==cooc_id).all()
    
    for cooc in query:
        matrix[cooc.ngramx_id][cooc.ngramy_id] = cooc.score
        matrix[cooc.ngramy_id][cooc.ngramx_id] = cooc.score

        ids[cooc.ngramx_id] = (field1, cooc.ngramx_id)
        ids[cooc.ngramy_id] = (field2, cooc.ngramy_id)

        weight[cooc.ngramx_id] = weight.get(cooc.ngramx_id, 0) + cooc.score
        weight[cooc.ngramy_id] = weight.get(cooc.ngramy_id, 0) + cooc.score

    x = pd.DataFrame(matrix).fillna(0)

    if distance == 'conditional':
        x = x / x.sum(axis=1)
        #y = y / y.sum(axis=0)

        xs = x.sum(axis=1) - x
        ys = x.sum(axis=0) - x

        # top inclus ou exclus
        n = ( xs + ys) / (2 * (x.shape[0] - 1))
        # top generic or specific
        m = ( xs - ys) / (2 * (x.shape[0] - 1))

        n = n.sort(inplace=False)
        m = m.sort(inplace=False)

        nodes_included = 500 #int(round(size/20,0))
        #nodes_excluded = int(round(size/10,0))

        nodes_specific = 500 #int(round(size/10,0))
        #nodes_generic = int(round(size/10,0))

        # TODO use the included score for the node size
        n_index = pd.Index.intersection(x.index, n.index[:nodes_included])
        # Generic:
        #m_index = pd.Index.intersection(x.index, m.index[:nodes_generic])
        # Specific:
        m_index = pd.Index.intersection(x.index, m.index[-nodes_specific:])
        #m_index = pd.Index.intersection(x.index, n.index[:nodes_included])

        x_index = pd.Index.union(n_index, m_index)
        xx = x[list(x_index)].T[list(x_index)]

        # Removing unconnected nodes
        xxx = xx.values
        threshold = min(xxx.max(axis=1))
        matrix_filtered = np.where(xxx >= threshold, xxx, 0)
        #matrix_filtered = matrix_filtered.resize((90,90))

        G = nx.from_numpy_matrix(np.matrix(matrix_filtered))
        G = nx.relabel_nodes(G, dict(enumerate([ ids[id_][1] for id_ in list(xx.columns)])))
    
    elif distance == 'cosine':
        scd = defaultdict(lambda : defaultdict(int))

        for i in matrix.keys():
            for j in matrix.keys():
                numerator = sum(
                                [
                                matrix[i][k] * matrix[j][k]
                                    for k in matrix.keys()
                                    if i != j and k != i and k != j
                                ]
                            )
                
                denominator  = sqrt(
                                    sum([
                                    matrix[i][k] 
                                        for k in matrix.keys()
                                        if k != i and k != j #and matrix[i][k] > 0
                                       ])
                                    *
                                    sum([
                                    matrix[i][k] 
                                        for k in matrix.keys()
                                        if k != i and k != j #and matrix[i][k] > 0
                                       ])

                               )

                try:
                    scd[i][j] = numerator / denominator
                except Exception as error:
                    scd[i][j] = 0

        minmax = min([ max([ scd[i][j] for i in scd.keys()]) for j in scd.keys()])

        G = nx.DiGraph()
        G.add_edges_from(
                          [
                            (i, j, {'weight': scd[i][j]}) 
                                for i in scd.keys() for j in scd.keys()
                                if i != j and scd[i][j] > minmax and scd[i][j] > scd[j][i]
                          ]
                        )



    elif distance == 'distributional':
        mi = defaultdict(lambda : defaultdict(int))
        total_cooc = x.sum().sum()
        
        for i in matrix.keys():
            si = sum([matrix[i][j] for j in matrix[i].keys() if i != j])
            for j in matrix[i].keys():
                sj = sum([matrix[j][k] for k in matrix[j].keys() if j != k])
                if i!=j :
                    mi[i][j] = log( matrix[i][j] / ((si * sj) / total_cooc) )
        
        r = defaultdict(lambda : defaultdict(int))
        
        for i in matrix.keys():
            for j in matrix.keys():
                sumMin = sum(
                                [
                                min(mi[i][k], mi[j][k])
                                    for k in matrix.keys()
                                    if i != j and k != i and k != j and mi[i][k] > 0
                                ]
                            )
                
                sumMi  = sum(
                                [
                                mi[i][k] 
                                    for k in matrix.keys()
                                    if k != i and k != j and mi[i][k] > 0
                                ]
                            )

                try:
                    r[i][j] = sumMin / sumMi
                except Exception as error:
                    r[i][j] = 0
        
        # Need to filter the weak links, automatic threshold here
        minmax = min([ max([ r[i][j] for i in r.keys()]) for j in r.keys()])

        G = nx.DiGraph()
        G.add_edges_from(
                          [
                            (i, j, {'weight': r[i][j]}) 
                                for i in r.keys() for j in r.keys()
                                if i != j and r[i][j] > minmax and r[i][j] > r[j][i]
                          ]
                        )
        
#        degree_max = max([(n, d) for n,d in G.degree().items()], key=itemgetter(1))[1]
#        nodes_to_remove = [n for (n,d) in G.degree().items() if d <= round(degree_max/2)]
#        G.remove_nodes_from(nodes_to_remove)

    # Removing too connected nodes (find automatic way to do it)
    #edges_to_remove = [ e for e in G.edges_iter() if

    #   nodes_to_remove = [n for n in degree if degree[n] <= 1]
    #   G.remove_nodes_from(nodes_to_remove)



    def getWeight(item):
        return item[1]
#    
#    node_degree = sorted(G.degree().items(), key=getWeight, reverse=True)
#    #print(node_degree)
#    nodes_too_connected = [n[0] for n in node_degree[0:(round(len(node_degree)/5))]]
#
#    for n in nodes_too_connected:
#        n_edges = list()
#        for v in nx.neighbors(G,n):
#            #print((n, v), G[n][v]['weight'], ":", (v,n), G[v][n]['weight'])
#            n_edges.append(((n, v), G[n][v]['weight']))
#
#        n_edges_sorted = sorted(n_edges, key=getWeight, reverse=True)
#        #G.remove_edges_from([ e[0] for e in n_edges_sorted[round(len(n_edges_sorted)/2):]])
#        #G.remove_edges_from([ e[0] for e in n_edges_sorted[(round(len(nx.neighbors(G,n))/3)):]])
#        G.remove_edges_from([ e[0] for e in n_edges_sorted[10:]])

    G.remove_nodes_from(nx.isolates(G))
    partition = best_partition(G.to_undirected())

    return(G,partition,ids,weight)

