from .parsing           import parse
from .ngrams_extraction import extract_ngrams

from .list_stop         import compute_stop
from .ngram_scores      import compute_occurrences_local, compute_tfidf
from .ngram_coocs_tempo import compute_coocs
from .score_specificity import compute_specificity
from .list_map          import compute_mapList     # TEST
from .ngram_groups      import compute_groups

from gargantext.util.db import session
from gargantext.models  import Node

from datetime           import datetime

def parse_extract(corpus):
    # retrieve corpus from database from id
    if isinstance(corpus, int):
        corpus_id = corpus
        corpus = session.query(Node).filter(Node.id == corpus_id).first()
        if corpus is None:
            print('NO SUCH CORPUS: #%d' % corpus_id)
            return
    # apply actions
    print('CORPUS #%d' % (corpus.id))
    parse(corpus)
    print('CORPUS #%d: parsed' % (corpus.id))
    extract_ngrams(corpus)
    print('CORPUS #%d: extracted ngrams' % (corpus.id))

    # -------------------------------
    # temporary ngram lists workflow
    # -------------------------------
    print('CORPUS #%d: [%s] starting ngram lists computation' % (corpus.id, t()))

    # -> stoplist: compute + write (=> Node and NodeNgram)
    stop_id = compute_stop(corpus)
    print('CORPUS #%d: [%s] new stoplist node #%i' % (corpus.id, t(), stop_id))

    # -> write local tfidf to Node and NodeNodeNgram
    ltfidf_id = compute_tfidf(corpus, scope="local")
    print('CORPUS #%d: [%s] new localtfidf node #%i' % (corpus.id, t(), ltfidf_id))

    # -> write global tfidf to Node and NodeNodeNgram
    gtfidf_id = compute_tfidf(corpus, scope="global")
    print('CORPUS #%d: [%s] new globaltfidf node #%i' % (corpus.id, t(), gtfidf_id))

    # ?? mainlist: compute + write (to Node and NodeNgram)
    # mainlist_id = compute_mainlist(corpus)
    # print('CORPUS #%d: [%s] new mainlist node #%i' % (corpus.id, t(), mainlist_id))

    # -> cooccurrences: compute + write (=> Node and NodeNodeNgram)
    cooc_id = compute_coocs(corpus, stop_id = None)
    print('CORPUS #%d: [%s] new cooccs node #%i' % (corpus.id, t(), cooc_id))

    # ?? specificity: compute + write (=> NodeNodeNgram)
    spec_id = compute_specificity(cooc_id=cooc_id, corpus=corpus)
    print('CORPUS #%d: [%s] new specificity node #%i' % (corpus.id, t(), cooc_id))

    # ?? maplist: compute + write (to Node and NodeNgram)
    # map_id = compute_stop(corpus)
    # print('CORPUS #%d: [%s] new maplist node #%i' % (corpus.id, t(), map_id))

    # -> write occurrences to Node and NodeNodeNgram # possible: factorize with tfidf
    occ_id = compute_occurrences_local(corpus)
    print('CORPUS #%d: [%s] new occs node #%i' % (corpus.id, t(), occ_id))

    # -> write groups to Node and NodeNgramNgram
    group_id = compute_groups(corpus, stoplist_id = None)
    print('CORPUS #%d: [%s] new grouplist node #%i' % (corpus.id, t(), group_id))


def t():
    return datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
