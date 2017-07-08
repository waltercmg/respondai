import datetime

from datetime import timedelta

date = datetime.datetime(2003,8,1)
for i in range(5): 
    date += datetime.timedelta(days=1)
    print(date.month) 

