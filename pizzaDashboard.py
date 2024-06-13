import psycopg2 as pg
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import pytz
import dash_bootstrap_components as dbc

# Verbindungsparameter
db_host = "localhost"
db_name = "pizzeria"
db_user = "postgres"
db_password = "password"
db_port = "5432"

# Verbindung zur Datenbank herstellen
connection = pg.connect(host=db_host, database=db_name, user=db_user, password=db_password, port=db_port,
                        client_encoding='utf-8')
cursor = connection.cursor()

berlin_tz = pytz.timezone('Europe/Berlin')

def get_order_date_range(cursor):
    try:
        sql_query = """
                    SELECT MIN("orderdate"::timestamp - INTERVAL '9 hours') as min_date, 
                           MAX("orderdate"::timestamp - INTERVAL '9 hours') as max_date
                    FROM orders;
                    """
        cursor.execute(sql_query)
        result = cursor.fetchone()
        return result[0], result[1]
    except Exception as e:
        print(f"Fehler beim Abrufen des Datumsbereichs: {e}")
        connection.rollback()
        return None, None

def fetch_orders(cursor, start_date, end_date):
    try:
        sql_query = f"""
                    SELECT "orderid", "orderdate"::timestamp - INTERVAL '9 hours' as "orderdate"
                    FROM orders
                    WHERE "orderdate" >= '{start_date}' AND "orderdate" <= '{end_date}';
                    """
        cursor.execute(sql_query)
        result = cursor.fetchall()
        df = pd.DataFrame(result, columns=["orderid", "orderdate"])
        df["orderdate"] = pd.to_datetime(df["orderdate"], errors='coerce')
        return df
    except Exception as e:
        print(f"Fehler beim Abrufen der Bestellungen: {e}")
        connection.rollback()
        return pd.DataFrame()

def get_store_data(cursor, year):
    if year is None:
        year = pd.Timestamp.now().year

    try:
        sql_query = f"""
                    SELECT s."latitude", s."longitude", s."city", COUNT(o."orderid") as order_count
                    FROM stores s
                    LEFT JOIN orders o ON s."storeid" = o."storeid" AND EXTRACT(YEAR FROM o."orderdate"::date) = {year}
                    GROUP BY s."latitude", s."longitude", s."city";
                    """
        cursor.execute(sql_query)
        results = cursor.fetchall()
        store_data = pd.DataFrame(results, columns=["lat", "lon", "City", "Order Count"])
        store_data["Order Count"] = pd.to_numeric(store_data["Order Count"], errors='coerce').fillna(0)
        store_data = store_data.dropna(subset=["lat", "lon", "Order Count"])
        return store_data
    except Exception as e:
        print(f"Fehler beim Abrufen von Daten der Stores: {e}")
        connection.rollback()
        return pd.DataFrame()

def create_year_dropdown():
    current_year = pd.Timestamp.now().year
    years = list(range(2020, 2023))
    dropdown_options = [{"label": str(year), "value": year} for year in years]
    dropdown = dcc.Dropdown(
        id='year-dropdown',
        options=dropdown_options,
        value=current_year
    )
    return dropdown

min_date, max_date = get_order_date_range(cursor)

dash.register_page(__name__, path='/pizza', name='Pizza Dashboard', title='Pizza Dashboard')

layout = dbc.Container([
    html.Div(className='container', children=[
        html.Div(className='row', children=[
            html.Div(className='col-6', children=[
                html.Div(className='analysis-container', children=[
                    html.Div(className='h2-container', children=[
                        html.H2("Order Dates")
                    ]),
                    html.Label("Choose a period:"),
                    html.Div(className='datePicker', children=[
                        dcc.DatePickerRange(
                            id='date-picker-range',
                            start_date=min_date,
                            end_date=max_date,
                            display_format='YYYY-MM-DD',
                            persistence=True,
                            persistence_type='session'
                        )
                    ]),
                    dcc.Graph(id='order-time-graph'),
                ]),
            ]),
            html.Div(className='col-6', children=[
                html.Div(className='analysis-container', children=[
                    html.Div(className='h2-container', children=[
                        html.H2("Location Analysis")
                    ]),
                    create_year_dropdown(),
                    html.Div(className='row', children=[
                        html.Div(className='col-6', children=[
                            dcc.Graph(id='choropleth-map', style={'height': '300px', 'width': '100%'})
                        ]),
                        html.Div(className='col-6', children=[
                            dcc.Graph(id='bar-chart', style={'height': '300px', 'width': '100%'})
                        ])
                    ])
                ]),
            ]),
        ]),
    ])
])

@dash.callback(
    Output('order-time-graph', 'figure'),
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_graph(start_date, end_date):
    df = fetch_orders(cursor, start_date, end_date)
    if df.empty:
        return px.bar()

    order_counts = df.groupby(df['orderdate'].dt.hour).size().reset_index(name='count')
    fig = px.bar(order_counts, x='orderdate', y='count',
                 labels={'orderdate': 'Hour', 'count': 'Number of orders'})
    fig.update_layout(title='Orders per hour',
                      xaxis_title='Time',
                      yaxis_title='Number of orders')
    return fig

@dash.callback(
    [Output('choropleth-map', 'figure'),
     Output('bar-chart', 'figure')],
    [Input('year-dropdown', 'value')]
)
def update_maps_and_chart(selected_year):
    store_data = get_store_data(cursor, selected_year)
    top_stores = store_data.nlargest(3, "Order Count").reset_index(drop=True)
    predefined_colors = ['#EF553B', '#EF553B', '#EF553B']
    top_stores['Color'] = predefined_colors
    color_map = {city: color for city, color in zip(top_stores["City"], predefined_colors)}
    store_data['Color'] = store_data['City'].map(color_map).fillna('#838b8b')

    fig = px.scatter_mapbox(store_data, lat="lat", lon="lon", hover_name="City", size="Order Count",
                            color='City', color_discrete_map=color_map,
                            zoom=4, height=300, width=440)
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

    for trace in fig.data:
        if trace.name not in top_stores['City'].values:
            trace.showlegend = False
            trace.marker.color = '#838b8b'

    bar_fig = px.bar(top_stores, x="City", y="Order Count", color="City",
                     color_discrete_map=color_map,
                     labels={"Order Count": "Number of orders", "City": "City"},
                     title="Top 3 stores with most sold products")

    return fig, bar_fig
