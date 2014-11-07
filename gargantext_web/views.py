from django.shortcuts import redirect
from django.shortcuts import render

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
from django.template import Context

#from documents.models import Project, Corpus, Document

from node.models import Language, ResourceType, Resource
from node.models import Node, NodeType, Node_Resource, Project, Corpus
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
    
    project = Node.objects.get(id=project_id)
    corpora = project.children.all()
    number  = project.children.count()


    # DONUT corpora representation
    
    donut_part = defaultdict(int)
    docs_total = 0
    list_corpora = defaultdict(list)
    
    for corpus in corpora:
        docs_count =  corpus.children.count()
        docs_total += docs_count
        
        corpus_view = dict()
        corpus_view['id']       = corpus.pk
        corpus_view['name']     = corpus.name
        corpus_view['count']      = corpus.children.count()

        for node_resource in Node_Resource.objects.filter(node=corpus):
            donut_part[node_resource.resource.type] += docs_count
            list_corpora[node_resource.resource.type.name].append(corpus_view)
    list_corpora = dict(list_corpora)

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

            if resource_type.name == "europresse_french":
                language    = Language.objects.get(iso2='fr')
            elif resource_type.name == "europresse_english":
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
            
            corpus.add_resource(
                    user=request.user, 
                    type=resource_type,
                    file=file
                    )

            try:
                corpus.parse_resources()
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
            'form': form, 
            'formResource': formResource, 
            'user': user,
            'date': date,
            'project': project,
            'donut' : donut,
            'list_corpora' : list_corpora,
            'number': number,
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
    
    #print(Document.objects.filter(corpus=c_id, user=request.user.pk).query)
    documents  = corpus.children.all()
    number = corpus.children.count()

    try:
        sources = defaultdict(int)
        for document in documents.all():
            sources[document.metadata['journal']] += 1
        
        sources_donut = []
        
        for source in sources.keys():
            source_count = dict()
            source_count['count'] = source['count']
            try:
                source_count['part'] = round(source_count['count'] * 100 / number)
            except:
                source_count['part'] = None
            source_count['source'] = source['source']
            sources_donut.append(source_count)
    except:
        sources_donut = []

    try:
        histo = [
                {'to_char': 2000, 'count': 13},
                {'to_char': 2001, 'count': 20},
                {'to_char': 2002, 'count': 5},
                {'to_char': 2003, 'count': 130},
                {'to_char': 2004, 'count': 300},
                ]

        first = parse(documents.first().metadata['publication_date'])
        last  = parse(documents.last().metadata['publication_date'])
        duree = first - last
        
        if duree.days > 365:
            date_format = 'YYYY'
            date_form = 'years'

            for document in documents:
                pass


        elif duree.days > 60:
            date_format = 'YYYY-MM'
            date_form = 'months'
        else:
            date_format = 'YYYY-MM-DD'
            date_form = 'days'

        try:
            dates = dict()

        except:
            pass
    
        
#        for e in date_range('1990-01', '1992-02', format=date_form):
#            print(e)
#        if date_format = 'YYYY':
#            while True:
#                if d -histo.append(d)
#        for d in dates:
#            histo.append(d)
         
    except:
        histo = [
                {'to_char': 2000, 'count': 13},
                {'to_char': 2001, 'count': 20},
                {'to_char': 2002, 'count': 5},
                {'to_char': 2003, 'count': 130},
                {'to_char': 2004, 'count': 300},
                ]
        #histo = None
       
    html = t.render(Context({\
            'user': user,\
            'date': date,\
            'project': project,\
            'corpus' : corpus,\
            'documents': documents,\
            'number' : number,\
            'dates' : histo,\
            }))
    
    return HttpResponse(html)


def delete_project(request, node_id):
    Node.objects.filter(id=node_id).all().delete()
    return HttpResponseRedirect('/projects/')

def delete_corpus(request, project_id, corpus_id):
    Node.objects.filter(id=corpus_id).all().delete()
    return HttpResponseRedirect('/project/' + project_id)

def explorer_graph(request):
    t = get_template('explorer.html')
    user = request.user
    date = datetime.datetime.now()

    html = t.render(Context({\
            'user': user,\
            'date': date,\
            }))
    
    return HttpResponse(html)

def explorer_matrix(request):
    t = get_template('matrix.html')
    user = request.user
    date = datetime.datetime.now()

    html = t.render(Context({\
            'user': user,\
            'date': date,\
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

def send_csv(request):
    '''
    Create the HttpResponse object with the appropriate CSV header.
    '''
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="somefilename.csv"'

    writer = csv.writer(response)

#    file = open('/srv/gargantext/static/js/d3/ndx.csv', 'r')
#    for line in file.readlines():
#        writer.writerow(line)

    writer.writerow(['date','open','high','low','close','volume','oi'])
    
#    writer.writerow(['12/19/2001','96.05','99.98','95.79','99.98','1260','0'])
#    writer.writerow(['12/20/2001','104.3','104.39','99.98','104.39','197','0'])
#    writer.writerow(['12/21/2001','109.07','109.13','103.73','109.13','28','0'])
#    writer.writerow(['12/24/2001','113.57','114.55','109.13','114.55','32','0'])
#    writer.writerow(['12/25/2001','120.09','120.25','114.55','120.25','15','0'])
#    writer.writerow(['12/26/2001','125.27','125.27','120.25','125.27','100','0'])
#    writer.writerow(['12/19/2002','96.05','99.98','95.79','99.98','1260','0'])
#    writer.writerow(['12/20/2002','104.3','104.39','99.98','104.39','197','0'])
#    writer.writerow(['12/21/2002','109.07','109.13','103.73','109.13','28','0'])
#    writer.writerow(['12/24/2002','113.57','114.55','109.13','114.55','32','0'])
#    writer.writerow(['12/25/2002','120.09','120.25','114.55','120.25','15','0'])
#    writer.writerow(['12/26/2002','125.27','125.27','120.25','125.27','100','0'])
#    writer.writerow(['12/19/2003','96.05','99.98','95.79','99.98','1260','0'])
#    writer.writerow(['12/20/2003','104.3','104.39','99.98','104.39','197','0'])
#    writer.writerow(['12/21/2003','109.07','109.13','103.73','109.13','28','0'])
#    writer.writerow(['12/24/2003','113.57','114.55','109.13','114.55','32','0'])
#    writer.writerow(['12/25/2003','120.09','120.25','114.55','120.25','15','0'])
#    writer.writerow(['12/26/2003','125.27','125.27','120.25','125.27','100','0'])
#    writer.writerow(['12/19/2004','96.05','99.98','95.79','99.98','1260','0'])
#    writer.writerow(['12/20/2004','104.3','104.39','99.98','104.39','197','0'])
#    writer.writerow(['12/21/2004','109.07','109.13','103.73','109.13','28','0'])
#    writer.writerow(['12/24/2004','113.57','114.55','109.13','114.55','32','0'])
#    writer.writerow(['12/25/2004','120.09','120.25','114.55','120.25','15','0'])
#    writer.writerow(['12/26/2004','125.27','125.27','120.25','125.27','100','0'])
#




    return response
