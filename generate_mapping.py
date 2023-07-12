import fiona
import csv
from shapely.geometry import shape
from shapely import Point
from shapely.validation import make_valid
from rtree import index
import os

COORDINATE_ERROR = 'No coordinates found for postcode'
CONSTITUENCY_ERROR = 'No constituency found for postcode'

england_shapefile_path = 'data/984162_2023_06_27_Final_recommendations_England_shp/2023_06_27_Final_recommendations_England.shp'
scotland_shapefile_path = 'data/bcs_final_recs_2023_review/All_Scotland_Final_Recommended_Constituencies_2023_Review.shp'
wales_shapefile_path = 'data/Wales Final Recs Shapefiles/Final Recommendations_region.shp'

old_constituency_id_mapping_path = 'data/ONSPD_MAY_2023_UK/Documents/Westminster Parliamentary Constituency names and codes UK as at 12_14.csv'
postcode_directory_path = 'data/ONSPD_MAY_2023_UK/Data/ONSPD_MAY_2023_UK.csv'

def create_constituency_index_and_list(shapefile_path, constituency_name_key):
    constituencies = []
    r_tree = index.Index()
    with fiona.open(shapefile_path) as boundaries:
        for i, constituency in enumerate(boundaries):
            constituency_shape = make_valid(shape(constituency['geometry']))
            constituencies.append((constituency.properties[constituency_name_key], constituency_shape))
            r_tree.insert(i, constituency_shape.bounds)
    return r_tree, constituencies

england_r_tree, england_constituencies = create_constituency_index_and_list(england_shapefile_path, 'Constituen')
scotland_r_tree, scotland_constituencies = create_constituency_index_and_list(scotland_shapefile_path, 'NAME')
wales_r_tree, wales_constituencies = create_constituency_index_and_list(wales_shapefile_path, 'Official_N')

def get_constituency(point, country):
    if country == 'E92000001':
        for candidateIndex in england_r_tree.intersection(point.bounds):
            constituency_name, constituency_shape = england_constituencies[candidateIndex]
            if point.within(constituency_shape):
                return constituency_name
    elif country == 'S92000003':
        for candidateIndex in scotland_r_tree.intersection(point.bounds):
            constituency_name, constituency_shape = scotland_constituencies[candidateIndex]
            if point.within(constituency_shape):
                return constituency_name
    elif country == 'W92000004':
        for candidateIndex in wales_r_tree.intersection(point.bounds):
            constituency_name, constituency_shape = wales_constituencies[candidateIndex]
            if point.within(constituency_shape):
                return constituency_name
            
    return ''

old_constituency_ids_dict = {}
with open(old_constituency_id_mapping_path, encoding='utf-8-sig') as old_id_file:
    old_ids = csv.DictReader(old_id_file)
    old_constituency_ids_dict = {old_id['PCON14CD']: old_id['PCON14NM'] for old_id in old_ids}

postcode_count = sum(1 for _ in open(postcode_directory_path)) - 1

if not os.path.exists('output'):
    os.makedirs('output')

with (
    open(postcode_directory_path) as postcodes_file,
    open('output/mapping.csv', mode='w') as output_file,
    open('output/errors.csv', mode='w') as error_file
):
    output_fieldnames = [
        'postcode',
        'old_constituency_name',
        'new_constituency_name',
        'ward'
    ]
    error_fieldnames = ['postcode', 'message']

    postcodes = csv.DictReader(postcodes_file)

    output_writer = csv.DictWriter(output_file, fieldnames=output_fieldnames)
    output_writer.writeheader()

    error_writer = csv.DictWriter(error_file, fieldnames=error_fieldnames)
    error_writer.writeheader()

    for i, postcode in enumerate(postcodes):
        if i % 10000 == 0:
            print(str(i) + ' of ' + str(postcode_count) + ', ' + '{:.1f}%'.format(100*i/postcode_count))

        if postcode['ctry'] not in ['E92000001','S92000003', 'W92000004']:
            continue

        if postcode['doterm'] != '':
            continue

        if postcode['oseast1m'] == '' or postcode['osnrth1m'] == '':
            print(', '.join([postcode['pcd'], COORDINATE_ERROR]))
            error_writer.writerow({
                error_fieldnames[0]: postcode['pcd'],
                error_fieldnames[1]: COORDINATE_ERROR
            })
            continue

        point = Point(int(postcode['oseast1m']), int(postcode['osnrth1m']))

        match = get_constituency(point, postcode['ctry'])
        
        if match == '':
            print(', '.join([postcode['pcd'], CONSTITUENCY_ERROR]))
            error_writer.writerow({
                error_fieldnames[0]: postcode['pcd'],
                error_fieldnames[1]: CONSTITUENCY_ERROR
            })
        else:
            fixed_ward = postcode['osward']
            if postcode['osward'] == 'E05006191':
                fixed_ward = 'E05014256'
            elif postcode['osward'] == 'E05012751':
                fixed_ward = 'E05015549'

            output_writer.writerow({
                output_fieldnames[0]: postcode['pcd'],
                output_fieldnames[1]: old_constituency_ids_dict[postcode['pcon']],
                output_fieldnames[2]: match,
                output_fieldnames[3]: fixed_ward
            })

with open('output/mapping.csv') as input_file:
    reader = csv.reader(input_file)
    with open('output/condensed_mapping.csv', mode='w') as condensed_output_file:
        writer = csv.writer(condensed_output_file)
        for row in reader:
            writer.writerow([row[0], row[2]])
