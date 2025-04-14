import pandas as pd
import dash
from dash import html, dcc, Input, Output
import plotly.express as px

# Load preprocessed data
inters = pd.read_csv('./data/inters.csv')
df = pd.read_csv('./data/df.csv')
df = df[df['accident_year'].isin([2024 - year for year in range(10)])]
# Initialize Dash app
app = dash.Dash(__name__)
app.title = "Collision Hotspots Map full df"


# Layout
app.layout = html.Div([

    html.Div([
        # LEFT: Controls
        html.Div([
            html.H2("San Francisco Collision Hotspots"),
            html.Label("Time Frame (Years):", style={"fontWeight": "bold", "margin-top": "20px"}),
            dcc.RangeSlider(
                id="year-range-slider",
                min=df['accident_year'].min(),
                max=df['accident_year'].max(),
                step=1,
                marks={year: str(year) for year in range(df['accident_year'].min(), df['accident_year'].max()+1)},
                value=[2019, 2024],  # default range
                allowCross=False
            ),
            html.Label("Severity:", style={"fontWeight": "bold", "margin-bottom": "10px"}),
            dcc.RadioItems(
                id="sort-by",
                options=[
                    {"label": "All collisions", "value": "total"},
                    {"label": "Fatal collisions", "value": "Fatal"},
                    {"label": "Severe collisions", "value": "Severe/Fatal"},
                    {"label": "Non-Severe collisions", "value": "Not Severe"},
                ],
                value="total",
                labelStyle={"display": "block", "margin-bottom": "5px"}
            ),
            html.Br(),
            html.Label("Number of intersections to show:", style={"fontWeight": "bold", "margin-top": "10px"}),
            dcc.Input(
                id="top-n-input",
                type="number",
                min=1,
                max=len(df),
                value=20,
                step=1,
                style={"width": "100px", "margin-top": "5px"}
            ),
            html.Div([
                dcc.Checklist(
                    id="show-all-toggle",
                    options=[{"label": "Show all", "value": "show_all"}],
                    value=[],  # Empty = unchecked
                    style={"margin-top": "10px"}
                )
            ]),
            # Modality checklist
            html.Label("Modalities:", style={"fontWeight": "bold", "margin-bottom": "10px"}),
            dcc.Checklist(
                id="modality-filter",
                options=[
                    {'label': 'Only Vehicles', "value": 'Vehicle(s) Only Involved'},
                    {'label': 'Vehicle - Pedestrian', "value": 'Vehicle-Pedestrian'},
                    {'label': 'Vehicle-Bicycle', "value": 'Vehicle-Bicycle'},
                    {'label': 'Bicycle Only', "value":'Bicycle Only'}
                ],
                value=[],
                style={"margin-top": "10px"}
            ),

            html.Label("Heatmap:", style={"fontWeight": "bold", "margin-bottom": "10px"}),
            dcc.RadioItems(
                id="color-toggle",
                options=[
                    {"label": "Fatal collisions", "value": "Fatal"},
                    {"label": "Severe collisions", "value": "Severe/Fatal"},
                ],
                value="Fatal",
                labelStyle={"display": "block", "margin-bottom": "5px"}
            ),
            
        ], style={
            "width": "100%",
            "padding": "20px",
            "textAlign": "left",
            "verticalAlign": "top",
        }),

        # RIGHT: Map
        html.Div([
            dcc.Graph(
                id="collision-map",
                config={"responsive": False}
            )
        ], style={"width": "100%", "padding": "10px"})

    ], style={  # THIS is the shared flex container
        "display": "flex",
        "flexDirection": "row"
    })
])


# Callback to update map
@app.callback(
    Output("collision-map", "figure"),
    Input("year-range-slider", "value"),
    Input("top-n-input", "value"),
    Input("sort-by", "value"),
    Input("show-all-toggle", "value"),
    Input('color-toggle', 'value'),
    Input('modality-filter','value')
)
def update_map(year_range, n, sort_by, show_all, color, modality):

    print(modality)
    year_start, year_end = year_range
    filtered_df = df[
        (df['accident_year'].between(year_start, year_end))]
    if modality:
        filtered_df = df[
            df['accident_year'].between(year_start, year_end) & 
            (df['dph_col_grp_description'].isin(modality))]

    grouped_by_inter = filtered_df.groupby('cnn_intrsctn_fkey')['collision_severity'].value_counts().reset_index()
    collision_severity_by_inter = grouped_by_inter.pivot(index='cnn_intrsctn_fkey', columns='collision_severity', values='count').fillna(0)
    order = ['Injury (Complaint of Pain)', 'Injury (Other Visible)', 'Injury (Severe)', 'Fatal']
    print("Available columns:", collision_severity_by_inter.columns.tolist())

    collision_severity_by_inter = collision_severity_by_inter[order]
    collision_severity_by_inter.columns = ['Complaint of Pain', 'Visible Injury', 'Severe', 'Fatal'] 
    collision_severity_by_inter['Not Severe'] = collision_severity_by_inter.apply(lambda row: row.iloc[0] + row.iloc[1], axis=1)
    collision_severity_by_inter['Severe/Fatal'] = collision_severity_by_inter.apply(lambda row: row.iloc[2] + row.iloc[3], axis=1)

    collision_severity_by_inter['total'] = (
        collision_severity_by_inter['Not Severe'] + collision_severity_by_inter['Severe/Fatal']
    )
    inters_subset = inters[['cnn', 'the_geom']]
    inters_subset = inters_subset.drop_duplicates(subset='cnn')

    collision_severity_by_inter = collision_severity_by_inter.join(
        inters_subset.set_index('cnn'), 
        how='left'
    )
    collision_severity_by_inter.dropna(inplace=True)

    collision_severity_by_inter[['lon', 'lat']] = collision_severity_by_inter['the_geom'].apply(
        lambda s: pd.Series(s[7:-1].split())
    ).astype(float)

    collision_severity_by_inter.drop(columns='the_geom', inplace=True)

    streets_by_cnn = (
        inters.groupby("cnn")["st_name"]
        .unique()  # or .tolist() if you want all (including repeats)
        .reset_index()
        .rename(columns={"st_name": "connected_streets"})
    )

    streets_by_cnn["connected_streets"] = streets_by_cnn["connected_streets"].apply(", ".join)
    streets_by_cnn= streets_by_cnn.set_index('cnn')

    collision_severity_by_inter = collision_severity_by_inter.join(
        streets_by_cnn,
        how='left')    
    
    if "show_all" in show_all:
        n = (collision_severity_by_inter[sort_by] > 0).sum()

    top_n = collision_severity_by_inter.sort_values(sort_by, ascending=False).head(n).reset_index()
    fig = px.scatter_map(
        top_n,
        lat="lat",
        lon="lon",
        size="total",
        color=color,
        color_continuous_scale="Viridis",  # or any other Plotly scale
        hover_name="connected_streets",
        hover_data={
        "connected_streets": False,
        "total": False,
        "Not Severe": True,
        "Severe": True,
        "Fatal": True,
        "lat": False,
        "lon": False
    },
        zoom=11.6,
        # height=800,
        # width = 500,

        center={"lat": 37.7489, "lon": -122.4394}
    )

    fig.update_layout(
        mapbox=dict(
            center={"lat": 37.7489, "lon": -122.4394},
            zoom=11.6
        ),
        height=800,
        width = 900,
        uirevision="lock-map"  # 👈 prevents map from resetting on updates
    )

    return fig


# Run the app
if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=8050)

