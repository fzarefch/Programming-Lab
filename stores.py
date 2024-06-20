import dash
from dash import html, dcc, callback, Input, Output, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd
import psycopg2 as pg
from geopy.distance import geodesic
from functools import lru_cache

dash.register_page(__name__, name='Stores', path='/stores')

# Verbindungsparameter
db_host = "localhost"
db_name = "postgres"
db_user = "postgres"
db_password = "password"
db_port = "5432"

# Verbindung zur Datenbank herstellen
connection = pg.connect(
    host=db_host,
    database=db_name,
    user=db_user,
    password=db_password,
    port=db_port
)

cursor = connection.cursor()


@lru_cache(maxsize=32)
def get_store_data():
    try:
        sql_query = """
                    SELECT s.storeid, s.latitude, s.longitude, s.city, COUNT(o.orderid) as order_count, COUNT(DISTINCT o.customerid) as customer_count
                    FROM stores s
                    LEFT JOIN orders o ON s.storeid = o.storeid
                    GROUP BY s.storeid, s.latitude, s.longitude, s.city;
                    """
        cursor.execute(sql_query)
        results = cursor.fetchall()
        return pd.DataFrame(results,
                            columns=["Store ID", "Latitude", "Longitude", "City", "Order Count", "Customer Count"])
    except Exception as e:
        print(f"Fehler beim Abrufen der Store-Daten: {e}")
        return pd.DataFrame()


@lru_cache(maxsize=32)
def get_sales_data(store_ids, start_date, end_date):
    try:
        store_ids_str = ', '.join(f"'{store_id}'" for store_id in store_ids)  # Convert list to comma-separated string
        sql_query = f"""
                    SELECT o.storeid, s.city, DATE(o.orderdate) as order_date, COUNT(oi.orderid) as sales_count, 
                    COUNT(DISTINCT o.customerid) as customer_count, SUM(p.price) as total_revenue
                    FROM orders o
                    LEFT JOIN orderitems oi ON o.orderid = oi.orderid
                    LEFT JOIN products p ON oi.sku = p.sku
                    LEFT JOIN stores s ON o.storeid = s.storeid
                    WHERE o.storeid IN ({store_ids_str}) AND DATE(o.orderdate) BETWEEN %s AND %s
                    GROUP BY o.storeid, s.city, order_date
                    ORDER BY order_date;
                    """
        cursor.execute(sql_query, (start_date, end_date))
        results = cursor.fetchall()
        sales_data = pd.DataFrame(results, columns=["Store ID", "City", "Order Date", "Sales Count", "Customer Count",
                                                    "Total Revenue"])
        return sales_data
    except Exception as e:
        print(f"Fehler beim Abrufen der Verkaufsdaten: {e}")
        return pd.DataFrame()


@lru_cache(maxsize=32)
def get_top_pizzas(store_ids, start_date, end_date):
    try:
        store_ids_str = ', '.join(f"'{store_id}'" for store_id in store_ids)  # Convert list to comma-separated string
        sql_query = f"""
                    SELECT o.storeid, p.name, COUNT(oi.orderid) as sales_count
                    FROM orders o
                    LEFT JOIN orderitems oi ON o.orderid = oi.orderid
                    LEFT JOIN products p ON oi.sku = p.sku
                    WHERE o.storeid IN ({store_ids_str}) AND DATE(o.orderdate) BETWEEN %s AND %s
                    GROUP BY o.storeid, p.name
                    ORDER BY o.storeid, sales_count DESC;
                    """
        cursor.execute(sql_query, (start_date, end_date))
        results = cursor.fetchall()
        pizza_data = pd.DataFrame(results, columns=["Store ID", "Pizza Name", "Sales Count"])

        top_pizzas = pizza_data.groupby('Store ID').apply(lambda x: x.nlargest(3, 'Sales Count')).reset_index(drop=True)

        return top_pizzas
    except Exception as e:
        print(f"Fehler beim Abrufen der Pizza-Daten: {e}")
        return pd.DataFrame()


@lru_cache(maxsize=32)
def get_customer_data():
    try:
        sql_query = """
                    SELECT customerid, latitude, longitude
                    FROM customers
                    LIMIT 1000  -- Limit the number of customers for demonstration purposes
                    """
        cursor.execute(sql_query)
        results = cursor.fetchall()
        return pd.DataFrame(results, columns=["Customer ID", "Latitude", "Longitude"])
    except Exception as e:
        print(f"Fehler beim Abrufen der Kundendaten: {e}")
        return pd.DataFrame()


store_data = get_store_data()
customer_data = get_customer_data()

# Dropdown-Optionen für Stores
city_options = [{'label': city, 'value': city} for city in store_data['City'].unique()]

layout = dbc.Container([
    dbc.Row([
        dbc.Col([html.H3('Store Locations')], width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=pd.to_datetime('2022-01-01'),
                end_date=pd.to_datetime('2022-12-31'),
                display_format='YYYY-MM-DD'
            )
        ], width=6),
        dbc.Col([
            dbc.Checklist(
                options=[{'label': 'Show Customer Count', 'value': 'show_customers'}],
                value=['show_customers'],
                id='show-customer-toggle',
                switch=True,
            ),
        ], width=6),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='store-map')
        ], width=12),
    ]),
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Legend:"),
                html.Div([
                    html.Span("•", style={"font-size": "20px", "color": "#440154FF"}), " Low Order Count",
                    html.Br(),
                    html.Span("•", style={"font-size": "20px", "color": "#FDE725FF"}), " High Order Count"
                ]),
                html.Div("Point size represents customer count.")
            ])
        ], width=12),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(id='city-dropdown', options=city_options, multi=True,
                         placeholder="Wählen Sie eine oder mehrere Städte")
        ], width=6),
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id='store-sales-info', style={'font-size': '20px', 'margin-top': '20px'})
        ], width=12),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='sales-bar-chart-orders')
        ], width=12),
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='sales-bar-chart-customers')
        ], width=12),
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id='store-info-boxes', style={'font-size': '20px', 'margin-top': '20px'})
        ], width=12),
    ]),
], className='container')


@callback(
    Output('store-map', 'figure'),
    Input('date-picker-range', 'start_date'),
    Input('date-picker-range', 'end_date'),
    Input('show-customer-toggle', 'value')
)
def update_store_map(start_date, end_date, show_customers):
    # Store map
    map_fig = px.scatter_mapbox(store_data, lat="Latitude", lon="Longitude", hover_name="Store ID",
                                color="Order Count", size="Customer Count",
                                color_continuous_scale=px.colors.sequential.Viridis, zoom=3, height=300)
    map_fig.update_layout(mapbox_style="open-street-map")
    map_fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

    return map_fig


@callback(
    [Output('city-dropdown', 'value'),
     Output('sales-bar-chart-orders', 'figure'),
     Output('sales-bar-chart-customers', 'figure'),
     Output('store-sales-info', 'children'),
     Output('store-info-boxes', 'children')],
    [Input('store-map', 'clickData'),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date'),
     Input('city-dropdown', 'value'),
     Input('sales-bar-chart-orders', 'clickData'),
     Input('sales-bar-chart-customers', 'clickData')]
)
def update_store_sales(map_click, start_date, end_date, selected_cities, click_orders, click_customers):
    ctx = callback_context
    triggered = ctx.triggered[0]['prop_id']

    if triggered == 'store-map.clickData':
        selected_store = map_click['points'][0]['hovertext']
        selected_city = store_data[store_data['Store ID'] == selected_store]['City'].values[0]
        if selected_cities is None:
            selected_cities = [selected_city]
        elif selected_city not in selected_cities:
            selected_cities.append(selected_city)

    if selected_cities is None or not selected_cities:
        return selected_cities, {}, {}, None, []

    filtered_store_data = store_data[store_data['City'].isin(selected_cities)]

    store_ids = filtered_store_data['Store ID'].tolist()

    # Convert store_ids list to tuple for caching
    store_ids_tuple = tuple(store_ids)

    # Fetch sales data for the selected date range
    sales_data = get_sales_data(store_ids_tuple, start_date, end_date)

    if sales_data.empty:
        sales_by_period_orders = pd.DataFrame(columns=['Day', 'City', 'Sales Count'])
        sales_by_period_customers = pd.DataFrame(columns=['Day', 'City', 'Customer Count'])
        bar_fig_orders = px.bar(sales_by_period_orders, x='Day', y='Sales Count', color='City',
                                title='Number of Orders Over Time', barmode='group')
        bar_fig_customers = px.bar(sales_by_period_customers, x='Day', y='Customer Count', color='City',
                                   title='Number of Customers Over Time', barmode='group')
        store_info_boxes = [html.P("No data available.")]
    else:
        # Check if zooming to days is required
        if click_orders:
            clicked_month = click_orders['points'][0]['x']
            start_date = pd.to_datetime(clicked_month).to_period('M').start_time
            end_date = pd.to_datetime(clicked_month).to_period('M').end_time
            sales_data = get_sales_data(store_ids_tuple, start_date, end_date)
            zoom_in = True
        else:
            zoom_in = False

        # Aggregate sales data by period
        if zoom_in:
            sales_data['Day'] = pd.to_datetime(sales_data['Order Date']).dt.to_period('D')
            sales_by_period_orders = sales_data.groupby(['Day', 'City'])['Sales Count'].sum().reset_index()
            sales_by_period_customers = sales_data.groupby(['Day', 'City'])['Customer Count'].sum().reset_index()
            sales_by_period_orders['Day'] = sales_by_period_orders['Day'].astype(str)
            sales_by_period_customers['Day'] = sales_by_period_customers['Day'].astype(str)
            bar_fig_orders = px.bar(sales_by_period_orders, x='Day', y='Sales Count', color='City',
                                    title='Number of Orders Over Time', barmode='group')
            bar_fig_customers = px.bar(sales_by_period_customers, x='Day', y='Customer Count', color='City',
                                       title='Number of Customers Over Time', barmode='group')
        else:
            sales_data['Month'] = pd.to_datetime(sales_data['Order Date']).dt.to_period('M')
            sales_by_month_orders = sales_data.groupby(['Month', 'City'])['Sales Count'].sum().reset_index()
            sales_by_month_customers = sales_data.groupby(['Month', 'City'])['Customer Count'].sum().reset_index()
            sales_by_month_orders['Month'] = sales_by_month_orders['Month'].astype(str)
            sales_by_month_customers['Month'] = sales_by_month_customers['Month'].astype(str)
            bar_fig_orders = px.bar(sales_by_month_orders, x='Month', y='Sales Count', color='City',
                                    title='Number of Orders Over Time', barmode='group')
            bar_fig_customers = px.bar(sales_by_month_customers, x='Month', y='Customer Count', color='City',
                                       title='Number of Customers Over Time', barmode='group')

        bar_fig_orders.update_layout(xaxis={'type': 'category'})
        bar_fig_customers.update_layout(xaxis={'type': 'category'})

        top_pizzas_data = get_top_pizzas(store_ids_tuple, start_date, end_date)

        # Combine top pizzas and proximity info in a single box for each store
        store_info_boxes = []
        for store_id in filtered_store_data['Store ID']:
            top_pizzas = top_pizzas_data[top_pizzas_data['Store ID'] == store_id]
            top_pizzas_list = html.Ul(
                [html.Li(f"{row['Pizza Name']}: {row['Sales Count']} sales") for _, row in top_pizzas.iterrows()])

            store_lat = filtered_store_data[filtered_store_data['Store ID'] == store_id]['Latitude'].values[0]
            store_lon = filtered_store_data[filtered_store_data['Store ID'] == store_id]['Longitude'].values[0]
            store_location = (store_lat, store_lon)
            customer_locations = customer_data[['Latitude', 'Longitude']].apply(tuple, axis=1)
            customers_within_1_mile = sum(
                geodesic(store_location, customer_location).miles <= 1 for customer_location in customer_locations)
            customers_within_10_miles = sum(
                geodesic(store_location, customer_location).miles <= 10 for customer_location in customer_locations)
            total_customers = len(customer_data)
            proximity_info = html.Div([
                html.P(f"{customers_within_1_mile / total_customers * 100:.2f}% of customers live within 1 mile"),
                html.P(f"{customers_within_10_miles / total_customers * 100:.2f}% within 10 miles")
            ])

            store_info_boxes.append(
                dbc.Card(
                    dbc.CardBody([
                        html.H4(f"Store {store_id}"),
                        html.H5("Top 3 Pizzas:"),
                        top_pizzas_list,
                        html.H5("Customer Proximity:"),
                        proximity_info
                    ]),
                    style={"margin-top": "20px"}
                )
            )

    return selected_cities, bar_fig_orders, bar_fig_customers, None, store_info_boxes

