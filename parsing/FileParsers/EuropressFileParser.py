import re
import locale
from lxml import etree
from datetime import datetime, date
from django.utils import timezone
import dateutil.parser

from .FileParser import FileParser
from ..NgramsExtractors import *



class EuropressFileParser(FileParser):
  
    def _parse(self, file):
        localeEncoding = "fr_FR"
        codif      = "UTF-8"
        count = 0

        if isinstance(file, str):
            file = open(file, 'rb')
        #print(file)
        contents = file.read()
        #print(len(contents))
        #return []
        encoding = self.detect_encoding(contents)
        #print(encoding)
        if encoding != "utf-8":
            try:
                contents = contents.decode("latin1", errors='replace').encode(codif)
            except :
                try:
                    contents = contents.decode(encoding, errors='replace').encode(codif)
                except Exception as error:
                    print(error)

        try:
            html_parser = etree.HTMLParser(encoding=codif)
            html = etree.fromstring(contents, html_parser)
            html_articles = html.xpath('/html/body/table')
        except:
            return []

        # initialize the list of metadata
        metadata_list = []
        # parse all the articles, one by one
        try:
            for html_article in html_articles:
                
                metadata = {}
                
                if len(html_article):
                    for name in html_article.xpath("./tr/td/span[@class = 'DocPublicationName']"):
                        if name.text is not None:
                            format_journal = re.compile('(.*), (.*)', re.UNICODE)
                            test_journal = format_journal.match(name.text)
                            if test_journal is not None:
                                metadata['source'] = test_journal.group(1)
                                metadata['volume'] = test_journal.group(2)
                            else:
                                metadata['source'] = name.text.encode(codif)

                    for header in html_article.xpath("./tr/td/span[@class = 'DocHeader']"):
                        try:
                            text = header.text
                        except Exception as error:
                            print(error)

                        
                        if isinstance(text, bytes):
                            text = text.decode(encoding)

                        format_date_fr = re.compile('\d*\s*\w+\s+\d{4}', re.UNICODE)
                        test_date_fr = format_date_fr.match(text)
                        
                        format_date_en = re.compile('\w+\s+\d+,\s+\d{4}', re.UNICODE)
                        test_date_en = format_date_en.match(text)

                        format_sect = re.compile('(\D+),', re.UNICODE)
                        test_sect = format_sect.match(text)
                        
                        format_page = re.compile(', p. (\w+)', re.UNICODE)
                        test_page = format_page.match(text)
                        
                        if test_date_fr is not None:
                            self.localeEncoding = "fr_FR"
                            locale.setlocale(locale.LC_ALL, localeEncoding)
                            if encoding != "utf-8":
                                text = text.replace('י', 'é')
                                text = text.replace('ű', 'û')
                                text = text.replace(' aot ', ' août ')


                            try :
                                metadata['publication_date'] = datetime.strptime(text, '%d %B %Y')
                            except :
                                try:
                                    metadata['publication_date'] = datetime.strptime(text, '%B %Y')
                                except :
                                    try:
                                        metadata['publication_date'] = dateutil.parser.parse(text)
                                    except Exception as error:
                                        print(error)
                                        print(text)
                                        pass
                        
                        if test_date_en is not None:
                            localeEncoding = "en_GB.UTF-8"
                            locale.setlocale(locale.LC_ALL, localeEncoding)
                            try :
                                metadata['publication_date'] = datetime.strptime(text, '%B %d, %Y')
                            except :
                                try :
                                    metadata['publication_date'] = datetime.strptime(text, '%B %Y')
                                except :
                                    pass

                        if test_sect is not None:
                            metadata['section'] = test_sect.group(1).encode(codif)
                        
                        if test_page is not None:
                            metadata['page'] = test_page.group(1).encode(codif)

                    metadata['title'] = html_article.xpath("string(./tr/td/span[@class = 'TitreArticleVisu'])").encode(codif)
                    metadata['text']  = html_article.xpath("./tr/td/descendant-or-self::*[not(self::span[@class='DocHeader'])]/text()")
                   
                    line = 0
                    br_tag = 10
                    for i in html_articles[count].iter():
                       # print line, br, i, i.tag, i.attrib, i.tail
                        if i.tag == "span":
                            if "class" in i.attrib:
                                if i.attrib['class'] == 'TitreArticleVisu':
                                    line = 1
                                    br_tag = 2
                        if line == 1 and i.tag == "br":
                            br_tag -= 1
                        if line == 1 and br_tag == 0:
                            try:
                                metadata['authors'] = str.title(etree.tostring(i, method="text", encoding=codif)).encode(codif)#.split(';')
                            except:
                                metadata['authors'] = 'not found'
                            line = 0
                            br_tag = 10
                    
                    
                    try:
                        if metadata['publication_date'] is not None or metadata['publication_date'] != '':
                            try:
                                back = metadata['publication_date']
                            except Exception as e: 
                                #print(e)
                                pass
                        else:
                            try:
                                metadata['publication_date'] = back
                            except Exception as e:
                                print(e)
                    except :
                        metadata['publication_date'] = timezone.now()

                    #if lang == 'fr':
                    #metadata['language_iso2'] = 'fr'
                    #elif lang == 'en':
                    #    metadata['language_iso2'] = 'en'
                    
                    
                    metadata['publication_year']  = metadata['publication_date'].strftime('%Y')
                    metadata['publication_month'] = metadata['publication_date'].strftime('%m')
                    metadata['publication_day']  = metadata['publication_date'].strftime('%d')
                    metadata['publication_date'] = ""

                    metadata['object_id'] = str(metadata['text'][-9])
                    metadata['text'].pop()
                    metadata['text'] = str(' '.join(metadata['text']))
                    metadata['text'] = str(re.sub('Tous droits réservés.*$', '', metadata['text']))

                    metadata['bdd']  = u'europresse'
                    metadata['url']  = u''
                    
                  #metadata_str = {}
                    for key, value in metadata.items():
                        metadata[key] = value.decode() if isinstance(value, bytes) else value
                    metadata_list.append(metadata)
                    count += 1
        
        except Exception as error:
            print(error)
            pass

#       from pprint import pprint
#       pprint(metadata_list)
#       return []
        return metadata_list


