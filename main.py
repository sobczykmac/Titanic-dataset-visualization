import pandas as pd
import re
import plotly.express as px
import pycountry
import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output
from dash import dash_table
import os
import csv
import requests

# data taken from https://github.com/datasciencedojo/datasets and then coy pasted to titanic.csv file
df = pd.read_csv("titanic.csv")

#----DATA CLEANING----

#nazwy_kolumn = list(df.columns)

#for kol in nazwy_kolumn:
#    l_pustych_pol = df[kol].isna().sum()
#    print(f"W kolumnie {kol} jest {l_pustych_pol} wartosci NaN")

#missing Age replaced with mean for each Pclass
df['Age'] = df['Age'].fillna(df.groupby('Pclass')['Age'].transform("mean"))


def embarked_to_nums(val):
    if val == 'S':
        val = 1
    elif val == 'C':
        val = 2
    elif val =='Q':
        val = 3
    else:
        val = 0
    return val


df_nums = df.drop(columns=['Name', 'Sex', 'Ticket', 'Cabin'])
df_nums['Embarked'] = df_nums['Embarked'].apply(embarked_to_nums)

# Missing values for Embarked replaced with median
df['Embarked'] = df['Embarked'].fillna(df['Embarked'].mode()[0])
#column Cabin dropped as there is no usage from it in further visualization
df.drop(['Cabin'], axis=1, inplace=True)



#----DATA MANIPULATION----


df["Title"] = df["Name"].str.split(',').str[1]
df["Title"] = df["Title"].str.split('.').str[0]



#Create new column from 'Sex'
def get_age_sex_category(row):
    if row['Sex'] == 'male':
        if row['Age'] < 18:
            return 'Boy'
        else:
            return 'Man'
    else:
        if row['Age'] < 18:
            return 'Girl'
        else:
            return 'Woman'


df['Age-Sex'] = df.apply(get_age_sex_category, axis=1)




API_KEY = os.environ['API']
name_country_pairs = []
nazwiska = df['Name'].str.split(',').str[0].values.tolist()
myset = set(nazwiska)
nazwiska_unique = list(myset)
nazwiska_api = nazwiska_unique[:450]
for name in nazwiska_api:
    url = f'https://v2.namsor.com/NamSorAPIv2/api2/json/country/{name}'
    headers = {
        'X-API-KEY': API_KEY,
        "Accept": 'application/json'}
    response = requests.get(url, headers=headers, verify=False)
    result = response.json()
    country = result['country']
    name_country_pairs.append([name, country])


#Create new file containing last names and corresponding ISO country codes

output_file = 'names_output.csv'

with open(output_file, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['LastName', 'Country'])
    writer.writerows(name_country_pairs)

print(f"Data saved successfully to {output_file}.")


#Reading new csv and upload it to new dataframe
csv_file = 'names_output.csv'
csv_df = pd.read_csv(csv_file)

df['Last Name'] = df['Name'].apply(lambda x: re.search('([A-Za-z]+),', x).group(1))


# Merge both data frames
titanic_df = pd.merge(df, csv_df, left_on='Last Name', right_on='LastName', how='left')



# Remove unnecessary column from merged df
titanic_df.drop(['LastName'], axis=1, inplace=True)



passengers_by_country = titanic_df.groupby('Country').size().reset_index(name='Passenger Count')

# Need 3-letter ISO codes to create map plot, therefore pycountry module is being used
iso2_to_iso3 = {country.alpha_2: country.alpha_3 for country in pycountry.countries}
passengers_by_country['Country - ISO-3'] = passengers_by_country['Country'].map(iso2_to_iso3)


# Create map plot
fig = px.choropleth(passengers_by_country, locations='Country - ISO-3', locationmode='ISO-3',
                    color='Passenger Count', hover_name='Country',
                    title='Passengers countries origin',
                    color_continuous_scale='YlOrRd')

fig.update_layout(geo=dict(showframe=False, showcoastlines=False))



# Defining columns to table in dashboard
table_columns = ['PassengerId', 'Survived', 'Name', 'Age-Sex', 'Country']

# Create dashboard table
table = dash_table.DataTable(
    id='data-table',
    columns=[{'name': col, 'id': col} for col in table_columns],
    data=titanic_df[table_columns].to_dict('records'),
    style_table={'overflowX': 'auto'},
    page_size=10,
)



title_counts = titanic_df['Title'].value_counts().head(5)

# Create plot Title
title_plot = px.bar(
    x=title_counts,
    y=title_counts.index,
    orientation='h',
    color=title_counts.index,
    color_continuous_scale='YlOrRd'
)

#Create plot Pclass vs. Survived
class_survival_data = titanic_df.groupby(['Pclass', 'Survived']).size().reset_index(name='Count')
fig_class = px.bar(class_survival_data, x='Count', y='Pclass', color='Survived',
             barmode='group', title='Pclass vs Survived',
             color_continuous_scale=["red", "green"], orientation='h')

# Tworzenie aplikacji Dash
app = dash.Dash(__name__)

# Definiowanie layoutu dashboardu
app.layout = html.Div([
    html.H1('Titanic Survival dataset analysis'),


    html.H2('Origin countries map'),
    html.Div(
        className='row',
        children=[
            html.Div(
                className='col-md-6',
                children=[
                    dcc.Graph(id='origin-map', figure=fig)
                ]
            ),
            html.H2('Gender vs Survival'),
            dcc.Graph(id='survival-gender-graph'),
            html.Div(
                className='col-md-6',
                children=[
                    html.H2('Passengers table'),
                    html.Div(
                        className='table-container',
                        children=table
                    )
                ]
            ),
            html.Div(
                    className='col-md-6',
                    children=[
                        html.H2('Passengers titles'),
                        dcc.Graph(id='title-count-plot', figure=title_plot)
                ]
            ),
            html.Div(
                    className='col-md-6',
                    children=[
                        html.H2('Pclass vs Survival'),
                        dcc.Graph(id='survival-class-plot', figure=fig_class)
                ]
            ),
        ]
    ),




])

# TCreate callback for map and gender plot
@app.callback(
    Output('survival-gender-graph', 'figure'),
    Input('origin-map', 'clickData')
)
def update_survival_gender_graph(clickData):
    selected_country = clickData['points'][0]['hovertext'] if clickData else None


    filtered_df = titanic_df
    if selected_country:
        filtered_df = titanic_df[titanic_df['Country'] == selected_country]


    survival_gender_data = filtered_df.groupby(['Sex', 'Survived']).size().reset_index(name='Count')


    fig = px.bar(survival_gender_data, x='Sex', y='Count', color='Survived',
                 barmode='group', title='Gender vs Survival graph',
                 color_continuous_scale=["red", "green"])
    return fig




if __name__ == '__main__':
    app.run_server(debug=True)


