import os
import sys
import petl
import pymssql
import configparser
import requests
import datetime
import json
import decimal

#get data from configuration file
config = configparser.ConfigParser()
try:
    config.read('ETLdemo.ini')
except Exception as e:
    print("could not read configuration file:" + str(e))
    sys.exit()

# read settings from configuration file
startDate = config['CONFIG']['startDate']
url = config['CONFIG']['url'] 
destServer = config['CONFIG']['Server']
destDatabase = config['CONFIG']['database']

# requests data from URL
try :
    BOCResponse = requests.get(url+startDate)
except Exception as e:
    print("could not make requests:" + str(e))
    sys.exit()

# initialize list of lists for data storage
BOCDates = []
BOCRates = []

# check reponse status and process BOC JSON object
if (BOCResponse.status_code == 200):
    BOCRaw = json.loads(BOCResponse.text)

    # extract observation data into column arrays
    for row in BOCRaw['observations']:
        BOCDates.append(datetime.datetime.strptime(row['d'], '%Y-%m-%d'))
        BOCRates.append(decimal.Decimal(row['FXUSDCAD']['v']))

    # create petl table from column arrays and rename the colum
    exchangeRate = petl.fromcolumns([BOCDates, BOCRates], header = ['date', 'rate'])

    # load expense document
    try:
        expenses = petl.io.xlsx.fromxlsx('data/Expenses.xlsx', sheet='Github')
    except Exception as e:
        print('could not open expenses.xlsx' + str(e))
        sys.exit()

    # join tables
    expenses = petl.outerjoin(exchangeRate, expenses, key='date')
    
    # fill down missing values
    expenses = petl.filldown(expenses, 'rate')

    # remove dates with no expences
    expenses = petl.select(expenses, lambda rec: rec.USD != None)

    # add CDN column
    expenses = petl.addfield(expenses, 'CAD', lambda rec: decimal.Decimal(rec.USD) * rec.rate)

    # initialize database connection
    try:
        dbConnection = pymssql.connect(server=destServer, database=destDatabase)
    except Exception as e:
        print("could not connect to database:" + str(e))
        sys.exit()

    # populate expenses database table
    try: 
        petl.io.todb(expenses, dbConnection, 'Expenses')
    except Exception as e:
        print('could not write to database:' + str(e))