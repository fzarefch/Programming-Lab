import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import psycopg2 as pg

dash.register_page(__name__, name='Stores', path='/stores')

# Verbindungsparameter
db_host = "localhost"
db_name = "postgres"
db_user = "postgres"
db_password = "password"
db_port = "5432"

# Verbindung zur Datenbank herstellen
connection = pg.connect(
    host=db_host, database=db_name, user=db_user, password=db_password, port=db_port, client_encoding='utf-8'
)
cursor = connection.cursor()

def get_stores_data():
    query = "SELECT name, sales FROM stores"
    cursor.execute(query)
    result = cursor.fetchall()
    data = pd.DataFrame(result, columns=['Store', 'Sales'])
    return data

layout = dbc.Container([
    dbc.Row([
        dbc.Col([html.H3('Store Sales')], width=12, className='row-titles')
    ]),
    dbc.Row([
        dbc.Col([], width=2),
        dbc.Col([
            dcc.Loading(id='stores-loading', type='circle', children=dcc.Graph(id='fig-stores', className='my-graph'))
        ], width=8),
        dbc.Col([], width=2)
    ], className='row-content')
])

@callback(
    Output('fig-stores', 'figure'),
    Input('fig-stores', 'id')
)
def update_stores_graph(_):
    stores_data = get_stores_data()
    fig = go.Figure(data=[
        go.Bar(name='Sales', x=stores_data['Store'], y=stores_data['Sales'])
    ])
    fig.update_layout(title='Sales by Store', xaxis_title='Store', yaxis_title='Sales', height=500)
    return fig
