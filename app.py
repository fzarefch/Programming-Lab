import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import psycopg2 as pg

# Initialisiere die Dash-App
app = dash.Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])
server = app.server

# Layout für die Dash-Anwendung
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),  # dcc.Location-Komponente hinzufügen
    dbc.NavbarSimple(
        children=[
            dbc.NavItem(dbc.NavLink("Stores", href="/stores")),
            dbc.NavItem(dbc.NavLink("Customers", href="/customers")),
            dbc.NavItem(dbc.NavLink("Products", href="/products")),
        ],
        brand="Dashboard",
        color="primary",
        dark=True,
    ),
    dash.page_container  # Platzhalter für den Inhalt der Seiten
])

if __name__ == '__main__':
    app.run_server(debug=True)
