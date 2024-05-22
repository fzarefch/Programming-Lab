import psycopg2 as pg
from dash import dcc, html, dash
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd

# Verbindungsparameter
db_host = "localhost"
db_name = "pizzeria"
db_user = "postgres"
db_password = "postgres"
db_port = "5432"

# Verbindung zur Datenbank herstellen
connection = pg.connect(host=db_host, database=db_name, user=db_user, password=db_password, port=db_port,
                        client_encoding='utf-8')
cursor = connection.cursor()


def get_order_date_range(cursor):
    """Fetches the minimum and maximum order dates from the 'Orders' table."""
    try:
        # SQL-Abfrage zum Abrufen des minimalen und maximalen Bestelldatums
        sql_query = """
                    SELECT MIN("orderDate") as min_date, MAX("orderDate") as max_date
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
    """Fetches orders from the 'Orders' table within a specified date range."""
    try:
        sql_query = f"""
                    SELECT "orderID", "orderDate"
                    FROM orders
                    WHERE "orderDate" >= '{start_date}' AND "orderDate" <= '{end_date}';
                    """
        cursor.execute(sql_query)
        result = cursor.fetchall()
        df = pd.DataFrame(result, columns=["orderID", "orderDate"])
        df["orderDate"] = pd.to_datetime(df["orderDate"], errors='coerce')
        return df
    except Exception as e:
        print(f"Fehler beim Abrufen der Bestellungen: {e}")
        connection.rollback()
        return pd.DataFrame()


def get_store_data(cursor, year):
    """Fetches store data including locations and number of orders from the 'Stores' and 'Orders' tables."""
    if year is None:
        year = pd.Timestamp.now().year  # Fallback auf das aktuelle Jahr

    try:
        # SQL-Abfrage zum Abrufen der Standorte der Stores und der Anzahl der Bestellungen pro Store für das gegebene Jahr
        sql_query = f"""
                    SELECT s."latitude", s."longitude", s."city", COUNT(o."orderID") as order_count
                    FROM stores s
                    LEFT JOIN orders o ON s."storeID" = o."storeID"
                    WHERE EXTRACT(YEAR FROM o."orderDate"::date) = {year}
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


# Funktion zur Erstellung des Dropdown-Menüs für Jahre
def create_year_dropdown():
    current_year = pd.Timestamp.now().year
    years = list(range(2020, 2023))  # Annahme: Daten sind von 2020 bis zum aktuellen Jahr verfügbar
    dropdown_options = [{"label": str(year), "value": year} for year in years]
    dropdown = dcc.Dropdown(
        id='year-dropdown',
        options=dropdown_options,
        value=current_year  # Standardwert auf das aktuelle Jahr setzen
    )
    return dropdown


# Minimal- und Maximaldatum aus der Datenbank abrufen
min_date, max_date = get_order_date_range(cursor)

# Dash-App initialisieren
app = dash.Dash(__name__, assets_folder='assets')

# Layout des Dashboards definieren
app.layout = html.Div([
    html.Div([
        html.H1("Pizzeria Dashboard")
    ], className='banner'),
    html.Div(className='container', children=[
        html.Div(className='analysis-container', children=[
            html.Div(className='h2-container', children=[
                html.H2("Order Dates")
            ]),
            dcc.Graph(id='order-time-graph', figure={
                'layout': {
                    'plot_bgcolor':'#D3D3D3',
                    'paper_bgcolor':'#D3D3D3',
                    'font':{
                        'color':'#ff0000'
                    }
                }}),
            html.Label("Choose a period:"),
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=min_date,
                end_date=max_date,
                display_format='YYYY-MM-DD',
                persistence=True,
                persistence_type='session'
            ),
        ]),
        html.Div(className='analysis-container', children=[
            html.Div(className='h2-container', children=[
                html.H2("Location Analysis")
            ]),
            create_year_dropdown(),  # Dropdown-Menü für Jahre hinzufügen
            html.Div(className='analysis-box', children=[
                dcc.Graph(id='choropleth-map', style={'background-color': 'rgba(0,0,0,0)', 'border': '1px solid #838b8b'})  # Choroplethenkarte hinzufügen
            ]),
            html.Div(className='analysis-box', children=[
                dcc.Graph(id='bar-chart', style={'background-color': 'rgba(0,0,0,0)', 'border': '1px solid #838b8b'})  # Balkendiagramm hinzufügen
            ])
        ]),
    ])
])


# Callback-Funktion für die Aktualisierung der Bestellzeitpunkte-Grafik basierend auf dem ausgewählten Zeitraum
@app.callback(
    Output('order-time-graph', 'figure'),
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_graph(start_date, end_date):
    df = fetch_orders(cursor, start_date, end_date)
    if df.empty:
        return px.bar()  # Leeres Diagramm zurückgeben, wenn keine Daten vorhanden sind

    order_counts = df.groupby(df['orderDate'].dt.hour).size().reset_index(name='count')
    fig = px.bar(order_counts, x='orderDate', y='count',
                 labels={'orderDate': 'Hour', 'count': 'Number of orders'})
    fig.update_layout(title='Orders per hour',
                      xaxis_title='Time',
                      yaxis_title='Number of orders')
    return fig


# Callback-Funktion für die Aktualisierung der Choroplethenkarte und des Balkendiagramms basierend auf dem ausgewählten Jahr
@app.callback(
    [Output('choropleth-map', 'figure'),
     Output('bar-chart', 'figure')],
    [Input('year-dropdown', 'value')]
)
def update_maps_and_chart(selected_year):
    # Daten für das ausgewählte Jahr abrufen
    store_data = get_store_data(cursor, selected_year)

    # Top 3 Stores mit den meisten Verkäufen abrufen
    top_stores = store_data.nlargest(3, "Order Count").reset_index(drop=True)

    # Farben für die Top 3 Stores festlegen
    predefined_colors = ['#EF553B', '#00CC96', '#636EFA']  # Farben für Platz 1, 2 und 3
    top_stores['Color'] = predefined_colors

    # Farben zu den Hauptdaten hinzufügen
    color_map = {city: color for city, color in zip(top_stores["City"], predefined_colors)}
    store_data['Color'] = store_data['City'].map(color_map).fillna('#838b8b')

    # Choroplethenkarte aktualisieren
    fig = px.scatter_mapbox(store_data, lat="lat", lon="lon", hover_name="City", size="Order Count",
                            color='City', color_discrete_map=color_map,
                            zoom=4, height=300, width=440)

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

    # Legende nur für die Top 3 Städte anzeigen
    for trace in fig.data:
        if trace.name not in top_stores['City'].values:
            trace.showlegend = False

    # Balkendiagramm erstellen
    bar_fig = px.bar(top_stores, x="City", y="Order Count", color="City",
                     color_discrete_map=color_map,
                     labels={"Order Count": "Number of orders", "City": "City"},
                     title="Top 3 stores with most sold products")

    return fig, bar_fig


# Dash-App starten
if __name__ == '__main__':
    app.run_server(debug=True)

# Verbindung schließen
cursor.close()
connection.close()

