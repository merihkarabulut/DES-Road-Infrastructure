import dash
import dash_core_components as dcc
import dash_html_components as html
import os
import pandas as pd
import plotly.plotly as py
import plotly.graph_objs as go
import colorlover as cl

mapbox_access_token = "PLEASE INSERT THE MAPBOX ACCESS TOKEN"

app = dash.Dash(__name__)
server = app.server

app.css.append_css({"external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"})

## Import cleaned data
df_roads = pd.read_csv('cleaned_data/roads.csv')
df_bridges = pd.read_csv('cleaned_data/bridges.csv')
df_traffic = pd.read_csv('cleaned_data/traffic.csv')
df_widths = pd.read_csv('cleaned_data/widths.csv')
df_traffic_agg = pd.read_csv('cleaned_data/traffic_aggregated.csv')

road_list_all = df_roads['road'].unique()
road_group_names = ['All', 'National Roads', 'Regional Roads', 'District Roads']
road_group_lists = {'All' :  [],
                    'National Roads': ["N" + str(a) for a in sorted(list(map(int, [item[1:] for item in road_list_all if item[0] == 'N'])))],
                    'Regional Roads': ["R" + str(a) for a in sorted(list(map(int, [item[1:] for item in road_list_all if item[0] == 'R'])))],
                    'District Roads': ["Z" + str(a) for a in sorted(list(map(int, [item[1:] for item in road_list_all if item[0] == 'Z'])))]}
road_group_lists['All'] = road_group_lists['National Roads'] + road_group_lists['Regional Roads']+road_group_lists['District Roads']
road_list_all = road_group_lists['All']

##App layout
app.layout = html.Div([
    html.H3('Bangladesh Road Infrastructure'),
    html.Div([
        html.Label('Classification Mode'),
        dcc.RadioItems(
            id='class-mode',
            options=[
                {'label': 'Segment', 'value': 'segmentNo'},
                {'label': 'Road', 'value': 'road'}
            ],
            value='road'
        ),
        dcc.Dropdown(id = 'selection-menu'),
        html.Label('Ranking mode:'),
        dcc.RadioItems(
            id='ranking-mode',
            options=[
                {'label': 'Vulnerability', 'value': 'vulnerability'},
                {'label': 'Criticality', 'value': 'criticality'},
                {'label': 'Overall Priority', 'value': 'priority'}
            ],
            value='vulnerability'
        ),
        html.Label('Bridge locations:'),
        dcc.RadioItems(
            id='bridge-mode',
            options=[
                {'label': 'Hide', 'value': 'none'},
                {'label': 'Categorize by type', 'value': 'type'},
                {'label': 'Categorize by condition', 'value': 'condition'}
            ],
            value='none'
        )
    ], style = {'columnCount': 3}),
    dcc.Graph(id='bridge-map')
    ])

##Map updating function
@app.callback(
    dash.dependencies.Output('bridge-map', 'figure'),
    [dash.dependencies.Input('selection-menu', 'value'),
     dash.dependencies.Input('class-mode', 'value'),
     dash.dependencies.Input('ranking-mode', 'value'),
     dash.dependencies.Input('bridge-mode', 'value')])
def update_graph(selection_menu_name, class_mode_name, ranking_mode_name, bridge_mode_name):
    sel_roads = []
    if class_mode_name == 'road':
        sel_roads = road_group_lists[selection_menu_name]
    else:
        if isinstance(selection_menu_name, str):
            sel_roads.append(selection_menu_name)
        else:
            sel_roads = selection_menu_name
    roads = df_roads[df_roads['road'].isin(sel_roads)]
    traffic = pd.DataFrame()
    if class_mode_name =='road':
        traffic = df_traffic_agg[df_traffic_agg['road'].isin(sel_roads)].copy(deep=True)
        roads['segmentNo'] = 1
    else:
        traffic = df_traffic[df_traffic['road'].isin(sel_roads)].copy(deep=True)
    top_segments = traffic.sort_values(by=ranking_mode_name,
                                       ascending = False).reset_index(drop=True).head(10).reset_index()
    roads.set_index('road', inplace=True)
    traffic.set_index(['road', 'segmentNo'], inplace = True)
    bridges_data = []
    if bridge_mode_name!='none':
        con_pallete = cl.scales['4']['div']['RdYlBu']
        if bridge_mode_name=='type':
            con_pallete = cl.scales['9']['qual']['Paired']
        bridges = df_bridges[df_bridges['road'].isin(sel_roads)]
        con_dict = {bridges[bridge_mode_name].unique()[i]: i for i in range(len(bridges[bridge_mode_name].unique()))}
        bridges['text'] = bridges['name'] + "<br>Condition: " + bridges['condition'] + "<br>Type: " + bridges['type']
        bridges_data = go.Data([
            go.Scattermapbox(
                lat=bridges[bridges[bridge_mode_name]==b].lat,
                lon=bridges[bridges[bridge_mode_name]==b].lon,
                text=bridges[bridges[bridge_mode_name]==b].text,
                mode='markers',
                hoverinfo='text',
                marker={
                    'size': 5,
                    'color': con_pallete[(12-con_dict[b])%9],
                    'opacity': 0.7
                },
                legendgroup=bridge_mode_name,
                name = b,
                #showlegend= False
            ) for b in bridges[bridge_mode_name].unique()
       ])
    pallete = "YlGnBu"
    reversed_flag = True
    if ranking_mode_name == 'vulnerability':
        pallete = 'YlOrRd'
    else:
        if ranking_mode_name == 'priority':
            pallete = 'Reds'
            reversed_flag = False
    col_array = cl.scales['9']['seq'][pallete]
    val_min = traffic[ranking_mode_name].min()
    val_max = traffic[ranking_mode_name].max()
    traffic['col_index'] = 8*(traffic[ranking_mode_name] - val_min)/(val_max-val_min)
    roads_data = []
    for r in sel_roads:
        for j in roads.loc[r].segmentNo.unique():
            seg_coords = roads.loc[r][roads.loc[r].segmentNo == j].reset_index()
            trace_name = r
            if class_mode_name == 'segmentNo':
                trace_name = r + "-" + str(j)
            seg_text = "<b>" + trace_name + "</b>" + "<br>Length: " + str(round(traffic.loc[r,j]['Km'],1)) + " km<br>Bridges: " + str(int(traffic.loc[r, j]['A_bridges'])) + " (A) + " + str(int(traffic.loc[r, j]['B_bridges'])) + " (B)<br>           + " + str(int(traffic.loc[r, j]['C_bridges'])) + " (C) + " + str(int(traffic.loc[r, j]['D_bridges'])) + " (D)<br>Lanes: " + str(round(traffic.loc[r, j]['nrLanes'],1)) + "<br>Width: " + str(round(traffic.loc[r, j]['width'])) + " m<br>AADT: " + str(int(traffic.loc[r, j]['AADT'])) + "<br>Vulnerability: " + str(round(traffic.loc[r, j]['vulnerability'],1)) + "<br>Criticality: " + str(round(traffic.loc[r, j]['criticality'],1)) + "<br>Priority: " + str(round(traffic.loc[r, j]['priority'],1))
            seg_coords['color'] = traffic.loc[r, j][ranking_mode_name]
            trace_width = traffic.loc[r,j]['width']*10/30
            trace_color =  col_array[int(traffic.loc[r,j]['col_index'])]
            roads_data.append(
                go.Scattermapbox(
                    lat = seg_coords.lat,
                    lon = seg_coords.lon,
                    text = seg_text,
                    mode='lines',
                    hoverinfo='text',
                    line = {
                        'width': trace_width,
                        'color': trace_color
                    },
                    showlegend = False
                )
            )
    tick_values = [traffic[ranking_mode_name].min(), traffic[ranking_mode_name].mean(), traffic[ranking_mode_name].max()]
    tick_text = ['Min: '+ str(round(tick_values[0],1)),
                 'Mean: '+ str(round(tick_values[1],1)),
                 'Max: ' + str(round(tick_values[2],1))]
    roads_data.append(
        go.Scattermapbox(
            lat=traffic.lat,
            lon=traffic.lon,
            hoverinfo='none',
            mode='markers',
            marker = {
                'color': traffic[ranking_mode_name],
                'colorscale': pallete,
                'reversescale': reversed_flag,
                'opacity': 0,
                'showscale': True,
                'colorbar': {
                            'len': 0.33,
                    'x': 0.99,
                    'y': 0.01,
                            'xanchor': "right",
                            'yanchor': "bottom",
                            'nticks': 3,
                            'tickvals': tick_values,
                            'ticktext': tick_text
                        }
                },
            showlegend=False
        )
    )
    rank_data = []
    top_segments['name'] = ""
    if(class_mode_name == 'road'):
        top_segments['name'] = top_segments['road']
    else:
        top_segments['name'] = [top_segments.road[i]+"-"+str(top_segments.segmentNo[i]) for i in range(len(top_segments))]

    rank_data = []
    for i in range(len(top_segments)):
        rank_data.append(
            go.Scattermapbox(
                lat = [top_segments.loc[i, 'lat']],
                lon = [top_segments.loc[i, 'lon']],
                text =  str(i+1),
                hoverinfo = 'none',
                mode='text+markers',
                marker = {
                    'size': 20,
                    'color':  col_array[int(traffic.loc[top_segments.loc[i,'road'],
                                                        top_segments.loc[i,'segmentNo']]['col_index'])],
                    'opacity': 1
                },
                textfont={
                    'family':'Roboto',
                    'size':18,
                    'color':'white'},
                showlegend = True,
                name = "#" + str(i+1) + ": " + top_segments.loc[i, 'name'] + " (" + str(round(top_segments.loc[i, ranking_mode_name],1)) + ")"
            )
        )
    rank_data.append(
        go.Scattermapbox(
            lat = [52.078534],
            lon = [4.320183],
            text =  "#epalife",
            hoverinfo = 'name',
            mode='text+markers',
            marker = {
                'size': 10,
                'color':  'red',
                'opacity': 0.5
            },
            hoverlabel ={
                'namelength': -1,
                'bgcolor' : 'red',
                'font': {
                    'color': 'white',
                    'size': 15
                }
            },
            textposition = 'topcenter',
            textfont={
                'family':'Roboto',
                'size':20,
                'color':'red'},
            showlegend = False,
            name = u'😑'
        )
    )
    layout = go.Layout(
        autosize=False,
        width = 1800,
        height= 800,
        hovermode='closest',
        mapbox=dict(
            accesstoken=mapbox_access_token,
            bearing=0,
            center=dict(
                lat = (roads.lat.min()+roads.lat.max())/2,
                lon = (roads.lon.min()+roads.lon.max())/2
            ),
            pitch=0,
            zoom=7,
            style='light'
        )
    )
    updatemenus=list([
    dict(
        buttons=list([
            dict(
                args=['mapbox.style', 'light'],
                label='Light',
                method='relayout'
            ),
            dict(
                args=['mapbox.style', 'dark'],
                label='Dark',
                method='relayout'
            ),
            dict(
                args=['mapbox.style', 'streets'],
                label='Streets',
                method='relayout'
            ),
            dict(
                args=['mapbox.style', 'outdoors'],
                label='Outdoors',
                method='relayout'
            ),
            dict(
                args=['mapbox.style', 'satellite'],
                label='Satellite',
                method='relayout'
            ),
            dict(
                args=['mapbox.style', 'satellite-streets'],
                label='Satellite with Streets',
                method='relayout'
            )
        ]),
        x = 0.01,
        xanchor = 'left',
        y = 0.99,
        yanchor = 'top',
        font = dict(size=10)
        ),
    ])
    annotations = list([
    dict(text='Map<br>Style', x=0.01, y=0.99,
         yref='paper', align='left',
         showarrow=False,font=dict(size=12))
    ])
    layout['updatemenus'] = updatemenus
    #layout['annotations'] = annotations
    return dict(data = roads_data + bridges_data  + rank_data, layout = layout)

#Dynamically updates the selection menu options  
@app.callback(
    dash.dependencies.Output('selection-menu', 'options'),
    [dash.dependencies.Input('class-mode', 'value')])
def update_selection_menu(class_mode_name):
    if class_mode_name == 'road':
        return  [{'label': i, 'value': i} for i in road_group_lists.keys()]
    else:
        return [{'label': i, 'value': i} for i in road_group_lists['All']]

@app.callback(
    dash.dependencies.Output('selection-menu', 'multi'),
    [dash.dependencies.Input('class-mode', 'value')])
def set_selection_menu_multi(class_mode_name):
    if class_mode_name == 'road':
        return False
    else:
        return True

@app.callback(
    dash.dependencies.Output('selection-menu', 'value'),
    [dash.dependencies.Input('selection-menu', 'options')])
def set_selection_menu_value(available_options):
    if available_options[0]['value']=='All':
        return available_options[1]['value']
    else:
        return available_options[0]['value']

if __name__ == '__main__':
    app.run_server(debug=True)
