import dash
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine, text
import datetime
import dash_bootstrap_components as dbc
from sklearn.cluster import KMeans

# Create Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SUPERHERO])
app.config.suppress_callback_exceptions = True
engine = create_engine('postgresql://postgres:Rayan1388@localhost:5432/pizza')

# Load data functions
def load_data(store_ids=None, start_date=None, end_date=None):
    start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

    if store_ids:
        placeholders = ','.join([':store_id' + str(i) for i in range(len(store_ids))])
        query = f"SELECT storeid, orderdate, total FROM orders WHERE storeid IN ({placeholders}) AND orderdate BETWEEN :start_date AND :end_date"
        params = {f'store_id{i}': store_id for i, store_id in enumerate(store_ids)}
        params['start_date'] = start_date
        params['end_date'] = end_date
    else:
        query = "SELECT storeid, orderdate, total FROM orders WHERE orderdate BETWEEN :start_date AND :end_date"
        params = {"start_date": start_date, "end_date": end_date}

    df = pd.read_sql(text(query), con=engine, params=params)
    return df

def get_store_options():
    query = "SELECT DISTINCT storeid FROM orders"
    df = pd.read_sql(query, con=engine)
    options = [{'label': f'Store {store_id}', 'value': store_id} for store_id in df['storeid']]
    return options

def get_date_range():
    query = "SELECT MIN(orderdate) AS min_date, MAX(orderdate) AS max_date FROM orders"
    with engine.connect() as connection:
        result = connection.execute(text(query)).fetchone()
        min_date, max_date = result
        return min_date.date(), max_date.date()

min_date, max_date = get_date_range()

def load_customer_data():
    customers = pd.read_sql("SELECT * FROM customers", engine)
    orders = pd.read_sql("SELECT * FROM orders", engine)
    order_items = pd.read_sql("SELECT * FROM orders_items", engine)
    products = pd.read_sql("SELECT * FROM products", engine)

    # Ensure order dates are in datetime format
    orders['orderdate'] = pd.to_datetime(orders['orderdate'])

    # Perform cluster analysis to identify customer segments based on purchase behavior
    customer_expenses = orders.groupby('customerid').agg({'total': 'sum'}).reset_index()

    kmeans = KMeans(n_clusters=3, random_state=0)
    customer_expenses['cluster'] = kmeans.fit_predict(customer_expenses[['total']])

    customers = customers.merge(customer_expenses[['customerid', 'cluster']], on='customerid', how='left')

    order_items = order_items.merge(products, on='sku')
    orders = orders.merge(order_items, on='orderid')
    orders = orders.merge(customers[['customerid', 'cluster']], on='customerid', how='left')

    segment_expenses = orders.groupby(['cluster', 'category'], observed=True).agg({'total': 'sum'}).reset_index()

    return customers, orders, segment_expenses

customers, orders, segment_expenses = load_customer_data()

# Navbar
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Home", href="#")),
        dbc.NavItem(dbc.NavLink("Sales Analysis", href="#")),
        dbc.NavItem(dbc.NavLink("Customer Segmentation", href="#")),
    ],
    brand="Pizza Store Dashboard",
    brand_href="#",
    color="primary",
    dark=True,
)

# App layout
app.layout = dbc.Container([
    navbar,
    dbc.Row([
        dbc.Col(html.H1("Pizza Store Sales Dashboard", className='text-center my-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(html.P("Select one or more stores and click 'Load Data' to display the sales data.",
                       className='text-center mb-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='store-dropdown',
                options=get_store_options(),
                placeholder="Select one or more stores to view detailed orders",
                multi=True,
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
        dbc.Col(
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=min_date,
                end_date=max_date,
                min_date_allowed=min_date,
                max_date_allowed=max_date,
                display_format='YYYY-MM-DD',
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Button('Load Data', id='load-data-btn', color='primary', className='mb-4 btn-lg btn-block', style={'border-radius': '12px'}),
            width=12, className='text-center'
        )
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Loading(
                id="loading-1",
                type="default",
                children=[
                    dbc.Card(
                        dbc.CardBody([
                            dcc.Graph(id='graph', style={'height': '300px', 'width': '100%'}),
                            dbc.Button("Full Screen", id="open-modal-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px'})
                        ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
                    )
                ]
            ), width=12
        )
    ]),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Total Sales by Store")),
            dbc.ModalBody(dcc.Graph(id='graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-graph",
        size="xl",
        is_open=False,
    ),
    dbc.Row([
        dbc.Col(html.H2("Customer and Product Segment Analysis", className='text-center my-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(html.P("Cluster analysis to identify customer segments based on purchase behavior.",
                       className='text-center mb-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='cluster-dropdown',
                options=[
                    {'label': 'Cluster 0', 'value': 0},
                    {'label': 'Cluster 1', 'value': 1},
                    {'label': 'Cluster 2', 'value': 2},
                    {'label': 'All Clusters', 'value': 'all'}
                ],
                value='all',
                placeholder="Select a cluster",
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
        dbc.Col(
            dcc.RangeSlider(
                id='date-slider',
                min=orders['orderdate'].dt.year.min(),
                max=orders['orderdate'].dt.year.max(),
                value=[orders['orderdate'].dt.year.min(), orders['orderdate'].dt.year.max()],
                marks={str(year): str(year) for year in range(orders['orderdate'].dt.year.min(), orders['orderdate'].dt.year.max() + 1)},
                step=None
            ), width=6
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(id='cluster-graph', style={'height': '300px', 'width': '100%'}),
                    dbc.Button("Full Screen", id="open-modal-cluster-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px', 'zIndex': 1100})
                ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
            ), width=12
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(id='expenses-graph', style={'height': '300px', 'width': '100%'}),
                    dbc.Button("Full Screen", id="open-modal-expenses-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px', 'zIndex': 1100})
                ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
            ), width=12
        )
    ]),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Customer Segments based on Geographic Data")),
            dbc.ModalBody(dcc.Graph(id='cluster-graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-cluster-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-cluster-graph",
        size="xl",
        is_open=False,
        style={'zIndex': 1100}
    ),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Expenses by Customer Segment and Product Category")),
            dbc.ModalBody(dcc.Graph(id='expenses-graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-expenses-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-expenses-graph",
        size="xl",
        is_open=False,
        style={'zIndex': 1100}
    )
], fluid=True)

# Callbacks for updating graphs
@app.callback(
    Output('graph', 'figure'),
    Output('graph-fullscreen', 'figure'),
    [Input('store-dropdown', 'value'),
     Input('load-data-btn', 'n_clicks'),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_data(store_ids, n_clicks, start_date, end_date):
    if not n_clicks:
        raise PreventUpdate

    if not store_ids:
        fig = px.line(title="No stores selected")
        return fig, fig

    df = load_data(store_ids, start_date, end_date)
    if df.empty:
        fig = px.line(title="No data available")
        return fig, fig

    if df['orderdate'].dtype == object or df['orderdate'].dtype != 'datetime64[ns]':
        df['orderdate'] = pd.to_datetime(df['orderdate'])

    df = df[df['total'] > 0]
    df['orderdate'] = df['orderdate'].dt.to_period('M').dt.to_timestamp()
    df_line = df.groupby(['storeid', 'orderdate'])['total'].sum().reset_index()

    fig = px.line(df_line, x='orderdate', y='total', color='storeid', title='Total Sales by Store', labels={
        'orderdate': 'Order Date', 'total': 'Total Sales', 'storeid': 'Store ID'})

    fig.update_layout(
        xaxis_title='Order Date',
        yaxis_title='Total Sales',
        xaxis=dict(
            tickformat='%Y-%m',
            tickmode='array',
            tickvals=df_line['orderdate'].unique(),
            ticktext=[d.strftime('%Y-%m') for d in df_line['orderdate'].unique()],
            tickangle=45
        ),
        yaxis=dict(range=[0, df_line['total'].max() + 10]),
        height=300,
        margin=dict(l=40, r=20, t=40, b=100),
        template='plotly_white'
    )

    return fig, fig

@app.callback(
    [Output('cluster-graph', 'figure'),
     Output('expenses-graph', 'figure'),
     Output('cluster-graph-fullscreen', 'figure'),
     Output('expenses-graph-fullscreen', 'figure')],
    [Input('cluster-dropdown', 'value'),
     Input('date-slider', 'value')]
)
def update_cluster_graphs(selected_cluster, date_range):
    filtered_orders = orders[
        (orders['orderdate'].dt.year >= date_range[0]) & (orders['orderdate'].dt.year <= date_range[1])]

    if selected_cluster != 'all':
        filtered_customers = customers[customers['cluster'] == selected_cluster].copy()
        filtered_orders = filtered_orders[filtered_orders['cluster'] == selected_cluster].copy()
    else:
        filtered_customers = customers.copy()

    filtered_customers.loc[:, 'cluster'] = pd.Categorical(filtered_customers['cluster'], categories=[0, 1, 2])
    filtered_orders.loc[:, 'cluster'] = pd.Categorical(filtered_orders['cluster'], categories=[0, 1, 2])

    fig_cluster = px.scatter_mapbox(filtered_customers, lat='latitude', lon='longitude', color='cluster',
                                    title='Customer Segments based on Geographic Data',
                                    mapbox_style="open-street-map", zoom=5, height=300)
    fig_cluster.update_layout(
        mapbox=dict(center=dict(lat=filtered_customers['latitude'].mean(), lon=filtered_customers['longitude'].mean())))
    fig_cluster.update_traces(marker=dict(size=5), selector=dict(mode='markers'))

    segment_expenses = filtered_orders.groupby(['cluster', 'category'], observed=True).agg(
        {'total': 'sum'}).reset_index()
    fig_expenses = px.bar(segment_expenses, x='category', y='total', color='cluster',
                          title='Expenses by Customer Segment and Product Category')

    fig_cluster_fullscreen = fig_cluster.update_layout(height=700)
    fig_expenses_fullscreen = fig_expenses.update_layout(height=700)

    return fig_cluster, fig_expenses, fig_cluster_fullscreen, fig_expenses_fullscreen

@app.callback(
    Output("modal-graph", "is_open"),
    [Input("open-modal-graph", "n_clicks"), Input("close-modal-graph", "n_clicks")],
    [State("modal-graph", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-cluster-graph", "is_open"),
    [Input("open-modal-cluster-graph", "n_clicks"), Input("close-modal-cluster-graph", "n_clicks")],
    [State("modal-cluster-graph", "is_open")],
)
def toggle_cluster_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-expenses-graph", "is_open"),
    [Input("open-modal-expenses-graph", "n_clicks"), Input("close-modal-expenses-graph", "n_clicks")],
    [State("modal-expenses-graph", "is_open")],
)
def toggle_expenses_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

if __name__ == '__main__':
    app.run_server(debug=True)
import dash
from dash import html, dcc, Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine, text
import datetime
import dash_bootstrap_components as dbc
from sklearn.cluster import KMeans

# Create Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SUPERHERO])
app.config.suppress_callback_exceptions = True
engine = create_engine('postgresql://postgres:Rayan1388@localhost:5432/pizza')

# Load data functions
def load_data(store_ids=None, start_date=None, end_date=None):
    start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

    if store_ids:
        placeholders = ','.join([':store_id' + str(i) for i in range(len(store_ids))])
        query = f"SELECT storeid, orderdate, total FROM orders WHERE storeid IN ({placeholders}) AND orderdate BETWEEN :start_date AND :end_date"
        params = {f'store_id{i}': store_id for i, store_id in enumerate(store_ids)}
        params['start_date'] = start_date
        params['end_date'] = end_date
    else:
        query = "SELECT storeid, orderdate, total FROM orders WHERE orderdate BETWEEN :start_date AND :end_date"
        params = {"start_date": start_date, "end_date": end_date}

    df = pd.read_sql(text(query), con=engine, params=params)
    return df

def get_store_options():
    query = "SELECT DISTINCT storeid FROM orders"
    df = pd.read_sql(query, con=engine)
    options = [{'label': f'Store {store_id}', 'value': store_id} for store_id in df['storeid']]
    return options

def get_date_range():
    query = "SELECT MIN(orderdate) AS min_date, MAX(orderdate) AS max_date FROM orders"
    with engine.connect() as connection:
        result = connection.execute(text(query)).fetchone()
        min_date, max_date = result
        return min_date.date(), max_date.date()

min_date, max_date = get_date_range()

def load_customer_data():
    customers = pd.read_sql("SELECT * FROM customers", engine)
    orders = pd.read_sql("SELECT * FROM orders", engine)
    order_items = pd.read_sql("SELECT * FROM orders_items", engine)
    products = pd.read_sql("SELECT * FROM products", engine)

    # Ensure order dates are in datetime format
    orders['orderdate'] = pd.to_datetime(orders['orderdate'])

    # Perform cluster analysis to identify customer segments based on purchase behavior
    customer_expenses = orders.groupby('customerid').agg({'total': 'sum'}).reset_index()

    kmeans = KMeans(n_clusters=3, random_state=0)
    customer_expenses['cluster'] = kmeans.fit_predict(customer_expenses[['total']])

    customers = customers.merge(customer_expenses[['customerid', 'cluster']], on='customerid', how='left')

    order_items = order_items.merge(products, on='sku')
    orders = orders.merge(order_items, on='orderid')
    orders = orders.merge(customers[['customerid', 'cluster']], on='customerid', how='left')

    segment_expenses = orders.groupby(['cluster', 'category'], observed=True).agg({'total': 'sum'}).reset_index()

    return customers, orders, segment_expenses

customers, orders, segment_expenses = load_customer_data()

# Navbar
navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Home", href="#")),
        dbc.NavItem(dbc.NavLink("Sales Analysis", href="#")),
        dbc.NavItem(dbc.NavLink("Customer Segmentation", href="#")),
    ],
    brand="Pizza Store Dashboard",
    brand_href="#",
    color="primary",
    dark=True,
)

# App layout
app.layout = dbc.Container([
    navbar,
    dbc.Row([
        dbc.Col(html.H1("Pizza Store Sales Dashboard", className='text-center my-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(html.P("Select one or more stores and click 'Load Data' to display the sales data.",
                       className='text-center mb-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='store-dropdown',
                options=get_store_options(),
                placeholder="Select one or more stores to view detailed orders",
                multi=True,
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
        dbc.Col(
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=min_date,
                end_date=max_date,
                min_date_allowed=min_date,
                max_date_allowed=max_date,
                display_format='YYYY-MM-DD',
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Button('Load Data', id='load-data-btn', color='primary', className='mb-4 btn-lg btn-block', style={'border-radius': '12px'}),
            width=12, className='text-center'
        )
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Loading(
                id="loading-1",
                type="default",
                children=[
                    dbc.Card(
                        dbc.CardBody([
                            dcc.Graph(id='graph', style={'height': '300px', 'width': '100%'}),
                            dbc.Button("Full Screen", id="open-modal-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px'})
                        ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
                    )
                ]
            ), width=12
        )
    ]),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Total Sales by Store")),
            dbc.ModalBody(dcc.Graph(id='graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-graph",
        size="xl",
        is_open=False,
    ),
    dbc.Row([
        dbc.Col(html.H2("Customer and Product Segment Analysis", className='text-center my-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(html.P("Cluster analysis to identify customer segments based on purchase behavior.",
                       className='text-center mb-4 text-light'), width=12)
    ]),
    dbc.Row([
        dbc.Col(
            dcc.Dropdown(
                id='cluster-dropdown',
                options=[
                    {'label': 'Cluster 0', 'value': 0},
                    {'label': 'Cluster 1', 'value': 1},
                    {'label': 'Cluster 2', 'value': 2},
                    {'label': 'All Clusters', 'value': 'all'}
                ],
                value='all',
                placeholder="Select a cluster",
                className='mb-3',
                style={'color': '#000'}  # Set the text color to black
            ), width=6
        ),
        dbc.Col(
            dcc.RangeSlider(
                id='date-slider',
                min=orders['orderdate'].dt.year.min(),
                max=orders['orderdate'].dt.year.max(),
                value=[orders['orderdate'].dt.year.min(), orders['orderdate'].dt.year.max()],
                marks={str(year): str(year) for year in range(orders['orderdate'].dt.year.min(), orders['orderdate'].dt.year.max() + 1)},
                step=None
            ), width=6
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(id='cluster-graph', style={'height': '300px', 'width': '100%'}),
                    dbc.Button("Full Screen", id="open-modal-cluster-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px'})
                ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
            ), width=12
        )
    ]),
    dbc.Row([
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(id='expenses-graph', style={'height': '300px', 'width': '100%'}),
                    dbc.Button("Full Screen", id="open-modal-expenses-graph", color="primary", className="mt-2 btn-lg btn-block", style={'border-radius': '12px'})
                ], style={'box-shadow': '0 4px 8px 0 rgba(0,0,0,0.2)', 'transition': '0.3s', 'border-radius': '12px'})
            ), width=12
        )
    ]),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Customer Segments based on Geographic Data")),
            dbc.ModalBody(dcc.Graph(id='cluster-graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-cluster-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-cluster-graph",
        size="xl",
        is_open=False,
    ),
    dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Expenses by Customer Segment and Product Category")),
            dbc.ModalBody(dcc.Graph(id='expenses-graph-fullscreen', style={'height': '90vh'})),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-modal-expenses-graph", className="ml-auto btn-lg", style={'border-radius': '12px'})
            ),
        ],
        id="modal-expenses-graph",
        size="xl",
        is_open=False,
    )
], fluid=True)

# Callbacks for updating graphs
@app.callback(
    Output('graph', 'figure'),
    Output('graph-fullscreen', 'figure'),
    [Input('store-dropdown', 'value'),
     Input('load-data-btn', 'n_clicks'),
     Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_data(store_ids, n_clicks, start_date, end_date):
    if not n_clicks:
        raise PreventUpdate

    if not store_ids:
        fig = px.line(title="No stores selected")
        return fig, fig

    df = load_data(store_ids, start_date, end_date)
    if df.empty:
        fig = px.line(title="No data available")
        return fig, fig

    if df['orderdate'].dtype == object or df['orderdate'].dtype != 'datetime64[ns]':
        df['orderdate'] = pd.to_datetime(df['orderdate'])

    df = df[df['total'] > 0]
    df['orderdate'] = df['orderdate'].dt.to_period('M').dt.to_timestamp()
    df_line = df.groupby(['storeid', 'orderdate'])['total'].sum().reset_index()

    fig = px.line(df_line, x='orderdate', y='total', color='storeid', title='Total Sales by Store', labels={
        'orderdate': 'Order Date', 'total': 'Total Sales', 'storeid': 'Store ID'})

    fig.update_layout(
        xaxis_title='Order Date',
        yaxis_title='Total Sales',
        xaxis=dict(
            tickformat='%Y-%m',
            tickmode='array',
            tickvals=df_line['orderdate'].unique(),
            ticktext=[d.strftime('%Y-%m') for d in df_line['orderdate'].unique()],
            tickangle=45
        ),
        yaxis=dict(range=[0, df_line['total'].max() + 10]),
        height=300,
        margin=dict(l=40, r=20, t=40, b=100),
        template='plotly_white'
    )

    return fig, fig

@app.callback(
    [Output('cluster-graph', 'figure'),
     Output('expenses-graph', 'figure'),
     Output('cluster-graph-fullscreen', 'figure'),
     Output('expenses-graph-fullscreen', 'figure')],
    [Input('cluster-dropdown', 'value'),
     Input('date-slider', 'value')]
)
def update_cluster_graphs(selected_cluster, date_range):
    filtered_orders = orders[
        (orders['orderdate'].dt.year >= date_range[0]) & (orders['orderdate'].dt.year <= date_range[1])]

    if selected_cluster != 'all':
        filtered_customers = customers[customers['cluster'] == selected_cluster].copy()
        filtered_orders = filtered_orders[filtered_orders['cluster'] == selected_cluster].copy()
    else:
        filtered_customers = customers.copy()

    filtered_customers.loc[:, 'cluster'] = pd.Categorical(filtered_customers['cluster'], categories=[0, 1, 2])
    filtered_orders.loc[:, 'cluster'] = pd.Categorical(filtered_orders['cluster'], categories=[0, 1, 2])

    fig_cluster = px.scatter_mapbox(filtered_customers, lat='latitude', lon='longitude', color='cluster',
                                    title='Customer Segments based on Geographic Data',
                                    mapbox_style="open-street-map", zoom=5, height=300)
    fig_cluster.update_layout(
        mapbox=dict(center=dict(lat=filtered_customers['latitude'].mean(), lon=filtered_customers['longitude'].mean())))
    fig_cluster.update_traces(marker=dict(size=5), selector=dict(mode='markers'))

    segment_expenses = filtered_orders.groupby(['cluster', 'category'], observed=True).agg(
        {'total': 'sum'}).reset_index()
    fig_expenses = px.bar(segment_expenses, x='category', y='total', color='cluster',
                          title='Expenses by Customer Segment and Product Category')

    fig_cluster_fullscreen = fig_cluster.update_layout(height=700)
    fig_expenses_fullscreen = fig_expenses.update_layout(height=700)

    return fig_cluster, fig_expenses, fig_cluster_fullscreen, fig_expenses_fullscreen

@app.callback(
    Output("modal-graph", "is_open"),
    [Input("open-modal-graph", "n_clicks"), Input("close-modal-graph", "n_clicks")],
    [State("modal-graph", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-cluster-graph", "is_open"),
    [Input("open-modal-cluster-graph", "n_clicks"), Input("close-modal-cluster-graph", "n_clicks")],
    [State("modal-cluster-graph", "is_open")],
)
def toggle_cluster_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-expenses-graph", "is_open"),
    [Input("open-modal-expenses-graph", "n_clicks"), Input("close-modal-expenses-graph", "n_clicks")],
    [State("modal-expenses-graph", "is_open")],
)
def toggle_expenses_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

if __name__ == '__main__':
    app.run_server(debug=True)
