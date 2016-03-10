from gargantext.util.db import *
from gargantext.util.db_cache import *
from gargantext.constants import *

from gargantext.util.db    import session, aliased, func
from gargantext.util.lists import WeightedMatrix

from gargantext.models        import User, Node, Ngram, NodeNgram

import re
from sqlalchemy import desc, asc
#from ngram.tools import insert_ngrams

def isStopWord(ngram, stop_words=None):
    '''
    ngram :: (Int, String) => (ngram_id, ngram_terms)
    stop_words :: Set of String
    (to avoid SQL query each time isStopWord is invoked, get in as parameter)
    '''
    word = ngram[1]

    if word in stop_words:
        return(True)

    compiled_regexes = []   # to compile them only once
    for regex in [
              "^.{1,2}$"
            , "(.*)\d(.*)"
            # , "(.*)(\.)(.*)"         trop fort (enlève les sigles !)
            , "(.*)(\,)(.*)"
            , "(.*)(< ?/?p ?>)(.*)"       # marques de paragraphes
            , "(.*)(study)(.*)"
            , "(.*)\b(xx|xi|xv)\b(.*)"
            , "(.*)(result)(.*)"
            , "(.*)(année|nombre|moitié)(.*)"
            , "(.*)(temps)(.*)"
            , "(.*)(%)(.*)"
            , "(.*)(\{)(.*)"
            , "(.*)(terme)(.*)"
            , "(.*)(différent)(.*)"
            , "(.*)(travers)(.*)"
            , "(.*)(:|\|)(.*)"
            ] :
        compiled_regexes.append(re.compile(regex))

    for format_regex in compiled_regexes:
        if format_regex.match(word):
            # print("STOPLIST += '%s' (regex: %s)" % (word, format_regex.pattern))
            return(True)

    return False

def create_gargantua_resources():
    gargantua_id = session.query(User.id).filter(User.username=="gargantua").first()
    project = Node(
            name="Resources",
            user_id=gargantua_id,
            typename="PROJECT")
    stopList = Node(name="STOPLIST", parent_id=project.id, user_id=gargantua_id, typename="STOPLIST")
    session.add(project)
    session.add(stopList)
    session.commit()

def compute_stop(corpus, stopList_id=None, debug=False):
    '''
    Create list of stop words.
    TODO do a function to get all stop words with social scores
    '''

    # Get the StopList if it exist or create a new one
    # At this step of development, a new StopList should be created
    if stopList_id == None:
        stopList_id = session.query(Node.id).filter(
            Node.parent_id==corpus.id,
            Node.typename == "STOPLIST"
            ).first()
        if stopList_id == None:
            stopList = Node(name="STOPLIST",
                        parent_id=corpus.id,
                        user_id=corpus.user_id,
                        typename="STOPLIST")
            session.add(stopList)
            session.commit()
            stopList_id = stopList.id

    # For tests only
    if debug == True:
        session.query(Node).filter(Node.id==stopList_id).delete()
        session.commit()

    # Get common resources, all common StopWords on the platform
    ## First get the id of the StopList of Gargantua super user
    gargantua_id = session.query(User.id).filter(User.username=="gargantua").first()
    rootStopList_id = session.query(Node.id).filter(
            Node.user_id  == gargantua_id,
            Node.typename == "STOPLIST"
            ).first()
    ## Then get all the stop words
    ## stop_words :: [String]
    stop_words = (session.query(Ngram.terms)
                         .join(NodeNgram, NodeNgram.ngram_id == Ngram.id)
                         .filter(NodeNgram.node_id == rootStopList_id)
                         .all()
                 )

    # print([n for n in stop_words])

    ## Get the ngrams
    ## ngrams :: [(Int, String, Int)]
    frequency = func.count( NodeNgram.weight )
    ngrams = (session.query( Ngram.id, Ngram.terms, frequency )
            .join( NodeNgram, NodeNgram.ngram_id == Ngram.id )
            .join( Node, Node.id == NodeNgram.node_id )
            .filter( Node.parent_id == corpus.id,
                     Node.typename == "DOCUMENT")
            .group_by( Ngram.id )
            .order_by( desc( frequency ) )
            #.limit(limit)
            .all()
            )

    ngrams_to_stop = filter(lambda x: isStopWord(x,stop_words=stop_words), ngrams)

    # print([n for n in ngrams_to_stop])

    stop = LISTTYPES["STOPLIST"]({ n[0] : -1 for n in ngrams_to_stop})
    # stop = LISTTYPES["STOPLIST"]([n[0] for n in ngrams_to_stop])
    stop.save(stopList_id)
    return stopList_id
