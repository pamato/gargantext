from django.shortcuts import redirect
from django.shortcuts import render

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
from django.template import Context

from node.models import Language, ResourceType, Resource, \
        Node, NodeType, Node_Resource, Project, Corpus, \
        Ngram, Node_Ngram, NodeNgramNgram, NodeNodeNgram

from node.admin import CorpusForm, ProjectForm, ResourceForm

from django.contrib.auth.models import User

import datetime
from itertools import *
from dateutil.parser import parse

from django.db import connection
from django import forms


from collections import defaultdict

from parsing.FileParsers import *

# SOME FUNCTIONS

def query_to_dicts(query_string, *query_args):
    """Run a simple query and produce a generator
    that returns the results as a bunch of dictionaries
    with keys for the column values selected.
    """
    cursor = connection.cursor()
    cursor.execute(query_string, query_args)
    col_names = [desc[0] for desc in cursor.description]
    while True:
        row = cursor.fetchone()
        if row is None:
            break
        row_dict = dict(zip(col_names, row))
        yield row_dict
    return

def date_range(start_dt, end_dt = None, format=None):
    if format is None:
        form = "%Y-%m-%d"
        d = 1

    elif format == "years":
        form = "%Y"
        d = 365
    
    elif format == "months":
        form = "%Y-%m"
        d = 30

    elif format == "days":
        form = "%Y-%m-%d"
        d = 1

    start_dt = datetime.datetime.strptime(start_dt, form)
    if end_dt: end_dt = datetime.datetime.strptime(end_dt, form)
    while start_dt <= end_dt:
        yield start_dt.strftime(form)
        start_dt += datetime.timedelta(days=d)

# SOME VIEWS

def home(request):
    '''
    Home describes the platform.
    A video draws the narratives.
    If not logged a project test is shown.
    '''
    t = get_template('home.html')
    user = request.user
    date = datetime.datetime.now()

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            }))
    
    return HttpResponse(html)

def projects(request):
    '''
    This view show all projects for each user.
    Each project is described with metadata that are updateded on each following view.
    To each project, we can link a resource that can be an image.
    '''
    if not request.user.is_authenticated():
        return redirect('/admin/logout/?next=%s' % request.path)
    
    t = get_template('projects.html')
    
    user = request.user
    date = datetime.datetime.now()
    
    project_type = NodeType.objects.get(name='Project')
    projects = Node.objects.filter(user=user, type_id = project_type.id).order_by("-date")
    number = len(projects)
 
    form = ProjectForm()
    if request.method == 'POST':
        # form = ProjectForm(request.POST)
        # TODO : protect from sql injection here
        name = str(request.POST['name'])
        if name != "" :
            Project(name=name, type=project_type, user=user).save()
            return HttpResponseRedirect('/projects/')
    else:
        form = ProjectForm()

    return render(request, 'projects.html', {
        'date': date,
        'form': form,
        'number': number,
        'projects': projects
        })

def project(request, project_id):
    '''
    This view represents all corpora in a panoramic way.
    The title sums all corpora
    The donut summerizes composition of the project.
    The list of lists enalbles to navigate throw it.
    '''

    if not request.user.is_authenticated():
        return redirect('/login/?next=%s' % request.path)

    try:
        offset = str(project_id)
    except ValueError:
        raise Http404()

    user = request.user
    date = datetime.datetime.now()
    
    type_corpus     = NodeType.objects.get(name='Corpus')
    type_document   = NodeType.objects.get(name='Document')
    
    type_whitelist  = NodeType.objects.get(name='WhiteList')
    type_blacklist  = NodeType.objects.get(name='BlackList')
    type_cooclist   = NodeType.objects.get(name='Cooccurrence')

    project = Node.objects.get(id=project_id)
    corpora = project.children.filter(type=type_corpus)
    number  = len(corpora)

    # DONUT corpora representation
    list_corpora    = defaultdict(list)
    donut_part      = defaultdict(int)
    docs_total      = 0
    
    # List of resources
    # filter for each project here
    whitelists      = ""#.children.filter(type=type_whitelist)
    blacklists      = ""#.children.filter(type=type_blacklist)
    cooclists       = ""#.children.filter(type=type_cooclist)
    
    for corpus in corpora:
        docs_count =  corpus.children.count()
        docs_total += docs_count
        
        corpus_view = dict()
        corpus_view['id']         = corpus.pk
        corpus_view['name']       = corpus.name
        corpus_view['count']      = corpus.children.count()
        
        for node_resource in Node_Resource.objects.filter(node=corpus):
            donut_part[node_resource.resource.type] += docs_count
            list_corpora[node_resource.resource.type.name].append(corpus_view)
    list_corpora = dict(list_corpora)

    if docs_total == 0 or docs_total is None:
        docs_total = 1

    donut = [ {'source': key, 
                'count': donut_part[key] , 
                'part' : round(donut_part[key] * 100 / docs_total) } \
                        for key in donut_part.keys() ]


    if request.method == 'POST':
        #form = CorpusForm(request.POST, request.FILES)
        #print(str(request.POST))
        name        = str(request.POST['name'])

        try:
            resource_type = ResourceType.objects.get(id=str(request.POST['type']))
        except Exception as error:
            print(error)
            resource_type = None
        
        try:
            file = request.FILES['file']
        except Exception as error:
            print(error)
            file = None

        #if name != "" and resource_type is not None and file is not None:
        try:
            parent      = Node.objects.get(id=project_id)
            node_type   = NodeType.objects.get(name='Corpus')
            
            if resource_type.name == "europress_french":
                language    = Language.objects.get(iso2='fr')
            elif resource_type.name == "europress_english":
                language    = Language.objects.get(iso2='en')
            
            try:
                corpus = Node(
                        user=request.user,
                        parent=parent,
                        type=node_type,
                        language=language,
                        name=name,
                        )
            except:
                corpus = Node(
                        user=request.user,
                        parent=parent,
                        type=node_type,
                        name=name,
                        )

            corpus.save()
            print(corpus.language)
            corpus.add_resource(
                    user=request.user,
                    type=resource_type,
                    file=file
                    )

            try:
                corpus.workflow()
                #corpus.workflow((), countdown=3)

            except Exception as error:
                print(error)

            return HttpResponseRedirect('/project/' + str(project_id))
        except Exception as error:
            print('ee', error)
            form = CorpusForm(request=request)
            formResource = ResourceForm()

    else:
        form = CorpusForm(request=request)
        formResource = ResourceForm()
       
    return render(request, 'project.html', {
            'form'          : form,
            'formResource'  : formResource,
            'user'          : user,
            'date'          : date,
            'project'       : project,
            'donut'         : donut,
            'list_corpora'  : list_corpora,
            'whitelists'    : whitelists,
            'blacklists'    : blacklists,
            'cooclists'     : cooclists,
            'number'        : number,
        })

def corpus(request, project_id, corpus_id):
    if not request.user.is_authenticated():
        return redirect('/login/?next=%s' % request.path)
    
    try:
        offset = str(project_id)
        offset = str(corpus_id)
    except ValueError:
        raise Http404()

    t = get_template('corpus.html')
    
    user = request.user
    date = datetime.datetime.now()
    
    project = Node.objects.get(id=project_id)
    corpus  = Node.objects.get(id=corpus_id)
    
    #documents  = corpus.children.all()
    #number = corpus.children.count()

#    try:
#        sources = defaultdict(int)
#        for document in documents.all():
#            sources[document.metadata['journal']] += 1
#        
#        sources_donut = []
#        
#        for source in sources.keys():
#            source_count = dict()
#            source_count['count'] = source['count']
#            try:
#                source_count['part'] = round(source_count['count'] * 100 / number)
#            except:
#                source_count['part'] = None
#            source_count['source'] = source['source']
#            sources_donut.append(source_count)
#    except:
#        sources_donut = []
    # Do a javascript query/api for that
    query_date = """
        SELECT
            id,
            metadata -> 'publication_year' as year,
            metadata -> 'publication_month' as month, 
            metadata -> 'publication_day' as day,
            metadata -> 'title'
        FROM
            node_node AS n
        WHERE
            n.parent_id = %d
        ORDER BY
            year, month, day DESC
        LIMIT
            20
        OFFSET
            %d
    """ % (corpus.id, 0)
    try:
        cursor = connection.cursor()

        cursor.execute(query_date)
        documents = list()
        while True:
            document = dict()
            row = cursor.fetchone()
            
            if row is None:
                break
            document['id']      = row[0]
            document['date']    = row[1] + '/' + row[2] + '/' + row[3]
            document['title']   = row[4]
            documents.append(document)
    except Exception as error:
        print(error)

    try:
        chart = dict()
        chart['first'] = parse(corpus.children.first().metadata['publication_date']).strftime("%Y, %m, %d")
        chart['last']  = parse(corpus.children.last().metadata['publication_date']).strftime("%Y, %m, %d")
        print(chart)
    except Exception as error:
        print(error)
       
    html = t.render(Context({\
            'user': user,\
            'date': date,\
            'project': project,\
            'corpus' : corpus,\
            'documents': documents,\
    #        'number' : number,\
            'dates' : chart,\
            }))
    
    return HttpResponse(html)

def delete_project(request, node_id):
    Node.objects.filter(id=node_id).all().delete()
    return HttpResponseRedirect('/projects/')

def delete_corpus(request, project_id, corpus_id):
    Node.objects.filter(id=corpus_id).all().delete()
    return HttpResponseRedirect('/project/' + project_id)

def explorer_graph(request, corpus_id):
    t = get_template('explorer.html')
    user = request.user
    date = datetime.datetime.now()
    corpus = Node.objects.get(id=corpus_id)

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            'corpus': corpus,\
            }))
    
    return HttpResponse(html)

def explorer_matrix(request, corpus_id):
    t = get_template('matrix.html')
    user = request.user
    date = datetime.datetime.now()
    corpus = Node.objects.get(id=corpus_id)

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            'corpus': corpus,\
            }))
    
    return HttpResponse(html)

def exploration(request):
    t = get_template('exploration.html')
    user = request.user
    date = datetime.datetime.now()

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            }))
    
    return HttpResponse(html)

def explorer_chart(request):
    t = get_template('chart.html')
    user = request.user
    date = datetime.datetime.now()

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            }))
    
    return HttpResponse(html)

import csv
from django.db import connection

def send_csv(request, corpus_id):
    '''
    Create the HttpResponse object with the appropriate CSV header.
    '''
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="data.csv"'

    writer = csv.writer(response)
    cursor = connection.cursor()

    cursor.execute("""
    SELECT
        metadata -> 'publication_year' as year,
        metadata -> 'publication_month' as month,
        metadata -> 'publication_day' as day,
        COUNT(*)
    FROM
        node_node AS n
    WHERE
        n.parent_id = %s
    GROUP BY
        day, month, year
    ORDER BY
        year, month, day ASC
    """, [corpus_id])

    writer.writerow(['date','volume'])

    while True:
        row = cursor.fetchone()
        if row is None:
            break
        if row[0] is not None and row[1] is not None and row[2] is not None and row[3] is not None:
            writer.writerow([ str(row[0]) + '/' + str(row[1]) + '/' + str(row[2])  , str(row[3]) ])
        #dates['last']['day'] = documents.last().metadata['publication_day'])

    cursor.close()

    return response


# To get the data
from gargantext_web.api import JsonHttpResponse
from analysis.functions import get_cooc
import json

def node_link(request, corpus_id):
    '''
    Create the HttpResponse object with the node_link dataset.
    '''

   
    data = get_cooc(request=request, corpus_id=corpus_id, type="node_link")
    return JsonHttpResponse(data)

def adjacency(request, corpus_id):
    '''
    Create the HttpResponse object with the adjacency dataset.
    '''
    data = get_cooc(request=request, corpus_id=corpus_id, type="adjacency")
    return JsonHttpResponse(data)

def graph_it(request):
    '''The new multimodal graph.'''
    t = get_template('graph-it.html')
    user = request.user
    date = datetime.datetime.now()
    html = t.render(Context({
        'user': user,
        'date': date,
    }))    
    return HttpResponse(html)

def tests_mvc(request):
    '''Just a test page for Javascript MVC.'''
    t = get_template('tests/mvc.html')
    user = request.user
    date = datetime.datetime.now()
    html = t.render(Context({
        'user': user,
        'date': date,
    }))    
    return HttpResponse(html)

def ngrams(request):
    '''The ngrams list.'''
    t = get_template('ngrams.html')
    ngrams_list = list()
    
    for node_ngram in Node_Ngram.objects.filter(node_id=81246)[:20]:
        ngrams_list.append(node_ngram.ngram)

    user = request.user
    date = datetime.datetime.now()
    html = t.render(Context({
        'user': user,
        'date': date,
        'ngrams' : ngrams_list,
    }))    
    return HttpResponse(html)

def tfidf(request, corpus_id, ngram_id):
    """
    Takes IDs of corpus and ngram and returns list of relevent documents in json format
    according to TFIDF score (order is decreasing).
    """
    #it will receive something like:  api/tfidf/corpus_id/NGRAM1aNGRAM2aNGRAM3aNGRAM4...
    ngramsids = ngram_id.split("a")

    corpus = Node.objects.get(id=corpus_id)
    ngram  = Ngram.objects.get(id=ngramsids[0])#not used
    
    print("********-1 01*******")
    print("first ngram:")
    print(ngram)
    node_node_ngrams = NodeNodeNgram.objects.filter(nodex=corpus, ngram__in=ngramsids).order_by('-score')
    # print(node_node_ngrams)
    goodDict = {}
    for x in node_node_ngrams:
        # print(x.nodey)
        # print("\t",x.nodey.id)
        # print
        goodDict[x.nodey.id] = x.nodey
    print("imma here")
    print("arguments... nodes ids:")
    print(ngramsids)
    print ("with tfidf:")
    print(node_node_ngrams)
    print("corpus:")
    print(NodeNodeNgram.objects.filter(nodex=corpus))
    tfidf_list = []
    for x in goodDict:
        print(goodDict[x].metadata.keys())
        print
        pub = { "id":goodDict[x].id, 
                 "title":goodDict[x].metadata['title'], 
                 "publication_date":goodDict[x].metadata['publication_date'], 
                 "journal":goodDict[x].metadata['journal'] 
               }
        # tel = {'id': goodDict[x].id, "title":goodDict[x].metadata['title'], 'sape': 4139}
        # print(elem)
        tfidf_list.append(pub)
    print("********-1 02*******")
    
# only for tests
# TODO add test if metadata present
    # tfidf_list = [ dict(
    #     id=x.nodey.id,
    #     title=x.nodey.metadata['title'],
    #     publication_date=x.nodey.metadata['publication_date'],
    #     journal=x.nodey.metadata['journal'],
    #     #abstract=x.nodey.metadata['abstract'],
    #     )
    #     for x in node_node_ngrams]
    
    data = json.dumps(tfidf_list[:6]) # max 6 papers
    return JsonHttpResponse(data)




