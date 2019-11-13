import requests
import os

base = "https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial"
key = os.environ['KEY']


def get_driving_time(origin_lat, origin_lon, dest_lat, dest_lon):
    parameters = {'origins': "{},{}".format(origin_lat, origin_lon), 'destinations': "{},{}".format(dest_lat, dest_lon),
                  'key': key}
    r = requests.get(base, params=parameters)
    data = r.json()
    return round(int(data['rows'][0]['elements'][0]['duration']['value']) / 60, 2)
