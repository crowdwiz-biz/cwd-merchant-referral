import peewee, datetime
from playhouse.migrate import *
import config


if config.GENERAL['use_local_db']:
	database = peewee.SqliteDatabase(config.GENERAL['localdb_filename'])
else:
	database = peewee.PostgresqlDatabase(
	    config.GENERAL['pgsql_db'],  # Required by Peewee.
	    user=config.GENERAL['pgsql_db_user'],  # Will be passed directly to psycopg2.
	    password=config.GENERAL['pgsql_db_password'],
	    host=config.GENERAL['pgsql_db_host'],
		port = config.GENERAL['pgsql_db_port']
	)

class ITEMS(peewee.Model):
	from_account= peewee.TextField(default='', null = False)
	amount = peewee.IntegerField(default=0, null = True)
	asset = peewee.TextField(default='', null = False)
	op_id = peewee.IntegerField(default=0, null = True)
	ts = peewee.DateTimeField(default=datetime.datetime.now, null = True)
	blocktime = peewee.DateTimeField(default=datetime.datetime.now, null = True)
	deposit_status = peewee.IntegerField(default=0, null = True) # 0 - новый, 1 - выполнен, 2 - возврат

	class Meta:
		database = database

class BOT(peewee.Model):
	bc_login = peewee.TextField(default='', null=False)
	bc_id = peewee.TextField(default='', null=False)
	most_recent_op = peewee.IntegerField(default=0, null=False)
	statistics_id = peewee.TextField(default='', null=False)
	automatic_mode = BooleanField(default=True)

	class Meta:
		database = database

if __name__ == "__main__":
	try:
		ITEMS.create_table()
	except peewee.OperationalError:
		print("ITEMS table already exists!")
	try:
		BOT.create_table()
	except peewee.OperationalError:
		print("BOT table already exists!")