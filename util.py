import json
import os
import sys


def dumpToFile(name, data):
    with open(f"{name}.json", 'w') as outfile:
        json.dump(data, outfile)


def getJsonFile(name):
    with open(os.path.join(sys.path[0], f'{name}.json')) as configFile:
        return json.load(configFile)
