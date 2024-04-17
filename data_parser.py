import itertools
import os
import networkx as nx
from statistics import mode
import dearpygui.dearpygui as dpg
from datetime import date, timedelta
from SPARQLWrapper import SPARQLWrapper, JSON

from utils_parser import sparql_get_publications, sparql_extract_publications, name_converter, get_name, get_cpc


class Parser:
    def __init__(self):
        self.start_date = None
        self.end_date = None
        self.authority = '"EP"'
        self.graph_path = 'data/epo_collaboration_graph.net'
        self.corrected_graph_path = 'data/correct_epo_collaboration_graph.net'
        self.window()
        
    # --------------- Data extraction --------------- #
    def extract_category(self, cpc_codes):
        return mode([cpc[0] for cpc in cpc_codes])
    
    def get_data(self, publication):
        companies = []
        cpc_codes = []
        for pub in publication:
            if pub['title']['value'].split('/')[-1] == 'applicantVC':
                companies.append(pub['abstract']['value'])
            if pub['title']['value'].split('/')[-1] == 'classificationIPCInventive':
                cpc_codes.append(pub['abstract']['value'])
        if len(companies) > 1 and len(cpc_codes) > 0:
            companies = name_converter(get_name(companies))
            cpc_codes = get_cpc(cpc_codes)
            return (companies, '"'+self.extract_category(cpc_codes)+'"')
        
    def correct_graph(self):
        with open(self.graph_path, 'r') as file, open(self.corrected_graph_path, 'w') as outfile:
            for line in file:
                newline = line.replace(' 0.0 0.0 ellipse', '')
                outfile.write(newline)
    
    #------------- Callbacks ---------------- #
    def get_start_date(self, sender):
        vals = dpg.get_value(sender)
        vals['year'] = vals['year'] + 1900
        vals['month'] = vals['month'] + 1
        self.start_date = date(vals['year'], 
                               vals['month'], 
                               vals['month_day'])
        if self.end_date is None or self.end_date <= self.start_date:
            self.end_date = date(vals['year'], 
                                 vals['month'], 
                                 vals['month_day']) + timedelta(days=1)
            dpg.set_value('to', f'To (excluded): {self.end_date}')
        dpg.set_value('from', f'From (included): {self.start_date}')
            
    def get_end_date(self, sender):
        vals = dpg.get_value(sender)
        vals['year'] = vals['year'] + 1900
        vals['month'] = vals['month'] + 1
        self.end_date = date(vals['year'], 
                             vals['month'], 
                             vals['month_day'])
        if self.start_date is None or self.end_date <= self.start_date:
            self.start_date = date(vals['year'], 
                                   vals['month'], 
                                   vals['month_day']) - timedelta(days=1)
            dpg.set_value('from', f'From (included): {self.start_date}')
        dpg.set_value('to', f'To (excluded): {self.end_date}')        
        
    def get_authority(self, sender):
        self.authority = '"' + dpg.get_value(sender) + '"'
        
    def parse(self):
        dpg.set_value('saved', '')
        dpg.set_value('parsing_dates', f'Parsing dates: {self.start_date} - {self.end_date}')
        start = self.start_date
        for i in range((self.end_date - self.start_date).days // 7 + 1):
            if os.path.exists(self.corrected_graph_path):
                G = nx.read_pajek(self.corrected_graph_path)
            else:
                G = nx.MultiGraph(name='EPO Collaboration Graph')
        #for i in range((self.end_date - self.start_date).days):
            sparql = SPARQLWrapper(
                    "https://data.epo.org/"
                    "linked-data/query"
                )
            sparql.setReturnFormat(JSON)
            end = start + timedelta(days=7)
            if end > self.end_date:
                end = self.end_date
            dpg.set_value('progress', f'    Parsing now: {start} - {end} ({i+1}/{(self.end_date - self.start_date).days // 7 + 1})')
            applications = [application['pub']['value'] for application in sparql_get_publications('"'+str(start)+'"', '"'+str(end)+'"', self.authority, sparql)]
            for e, application in enumerate(applications):
                publication = sparql_extract_publications(application, sparql)
                if len(publication) > 0:
                    data = self.get_data(publication)
                    if data is not None:
                        companies, cpc_code = data
                        for company in companies:
                            if company not in G.nodes:
                                G.add_node(company)
                        if len(companies) == 2:
                            G.add_edge(companies[0], companies[1], label=cpc_code)
                        else:
                            for pair in itertools.pairwise(companies+[companies[0]]):
                                G.add_edge(pair[0], pair[1], label=cpc_code)
                    dpg.set_value('subprogress', f'        {e}/{len(applications)} publications parsed')
                        
            start = end
            del sparql
            nx.write_pajek(G, self.graph_path)
            dpg.set_value('subprogress', '')
            dpg.set_value('saved', f'Saved a graph with {len(G.nodes)} nodes and {len(G.edges)} edges to\n {self.corrected_graph_path}')
            self.correct_graph()
            
    
    # --------------- GUI ---------------- #
    def window(self):
        dpg.create_context()
        with dpg.window(label='EPO Data Parser', width=500, height=550):
            with dpg.group(horizontal=True):
                dpg.add_text('From (included):', tag='from', indent=10)
                dpg.add_text('To (excluded):', tag='to', indent=250)
            with dpg.group(horizontal=True):
                dpg.add_date_picker(default_value={'year': 123, 'month': 0, 'day': 1}, label='Start Date', tag='fromdp', indent=10, level=dpg.mvDatePickerLevel_Year, callback=self.get_start_date)
                dpg.add_date_picker(default_value={'year': 123, 'month': 0, 'day': 8},label='End Date', tag='todp', indent=250, level=dpg.mvDatePickerLevel_Year, callback=self.get_end_date)
            dpg.add_text('')
            dpg.add_text('Specify authority:')
            dpg.add_input_text(label='', callback=self.get_authority)
            dpg.add_button(label='Parse', callback=self.parse)
            dpg.add_text('')
            dpg.add_text('', tag='parsing_dates')
            dpg.add_text('')
            dpg.add_text('Progress: ')
            dpg.add_text('', tag='progress')
            dpg.add_text('', tag='subprogress')
            dpg.add_text('', tag='saved')
        dpg.create_viewport(title='EPO Data Parser', width=500, height=550, resizable=False)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

def get_start_date(sender):
    vals = dpg.get_value(sender)
    return date(vals['year'], vals['month'], vals['month_day'])

def get_start_date(sender):
    vals = dpg.get_value(sender)
    return date(vals['year'], vals['month'], vals['month_day'])
    
def main():
    Parser()


if __name__ == '__main__':
    main()