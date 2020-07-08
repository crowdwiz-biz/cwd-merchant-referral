from websocket import create_connection
from datetime import datetime, timedelta
import json, requests, logging, os, re, time, urllib
from os import listdir
from os.path import isfile, join

from crowdwiz import CrowdWiz
from crowdwiz.account import Account
from crowdwizbase.memo import decode_memo
from crowdwizbase.account import PublicKey, PrivateKey
import config

from textwrap import dedent

from models import ITEMS, BOT

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filename='referral_bot.log',
					level=logging.WARN)
logging.warn('Program started')

ws = create_connection(config.GENERAL['node'])
cwd = CrowdWiz(node=config.GENERAL['node'], keys=[config.GENERAL['wif']])

def pay_ref(order_id, blocktime, username, amount, bot_login):
	cwd = CrowdWiz(node=config.GENERAL['node'], keys=[config.GENERAL['wif']])
	order = ITEMS.get(ITEMS.op_id == order_id)
	pay_text=""
	if order.deposit_status == 0:
		# 
		# В этом месте вы можете выполнять какие-то важные действия связанные с оплатой заказа, например обновлять статус в CRM или отправлять уведомление по электронной почте
		#
		ref_referral=Account(username, blockchain_instance = cwd)
		for i in range(1,len(config.REFERRAL[bot_login])+1):
			try:
				ref_client=Account(ref_referral.name, blockchain_instance = cwd)
				ref_referral=Account(ref_client.get("referrer"), blockchain_instance = cwd)
				if ref_referral.name in config.BLACKLIST:
					ref_referral = Account(config.BLACKLIST[ref_referral.name], blockchain_instance = cwd)
				if (ref_referral.name != "committee-account"):
					ref_status=config.STATUSES[str(ref_referral.get('referral_status_type'))]
					ref_percent = config.REFERRAL[bot_login]['level%s' % str(i)][ref_status]
					if ref_percent>0:
						ref_amount=float(round(amount*100000*ref_percent)/100000)
						pay_text=pay_text + (config.MESSAGES['admin_message'] % (str(order_id), ref_referral.name,str(i), str(ref_amount)))
						cwd.transfer(ref_referral.name, ref_amount, "CWD", config.MESSAGES['referral_message'] % (str(i),username), account=bot_login)
			except Exception as e:
				print('Referral Error %s' % str(e))
				pass

		order.deposit_status = 1
		order.save()
		stm(pay_text+"%s Заявка успешно выполнена ✅" % (str(order_id)))

	else:
		stm("%s Заявка уже выполнена ⚠️" % (str(order_id)))


def get_block_date(block_num):
	ws = create_connection(config.GENERAL['node'])
	ws.send('{"jsonrpc": "2.0", "method": "get_block_header" "params": ["%s"], "id": 1}' % str(block_num))
	result = ws.recv()
	block =json.loads(result)
	ws.close()
	return datetime.strptime(block['result']['timestamp'], '%Y-%m-%dT%H:%M:%S')

def stm(text):
	if config.GENERAL['use_proxy']:
		proxies = config.PROXIES
	else:
		proxies = {}
	try:
		for admin in config.GENERAL['admin_accounts']:
			url='https://api.telegram.org/bot%s/sendMessage' % config.GENERAL['telegram_bot_token']
			r = requests.post(url, data = {'chat_id':admin, 'text':text}, proxies=proxies)
			reply=json.loads(r.text)
			if (reply['ok']):
				pass
			else:
				print('error')
	except Exception as e:
		print('error', str(e))

def get_new_operations(bot):
	cwd = CrowdWiz(node=config.GENERAL['node'], keys=[config.GENERAL['wif'],config.GENERAL['memo_wif']])
	account=Account(bot.bc_login, blockchain_instance = cwd)
	max_op_id = 0
	for his in account.history():
		op_id = his['id']
		int_op_id = int(op_id.split('.')[2])

		if int_op_id > max_op_id:
			max_op_id = int_op_id

		if int_op_id <= bot.most_recent_op:
			break

		if his['op'][0] == 0 and his['op'][1]['to'] == bot.bc_id:
			try:
				op_in_base=ITEMS.get(ITEMS.op_id == int_op_id)
			except:			
				acc = Account(his['op'][1]['from'], blockchain_instance = cwd)
				if (his['op'][1]['amount']['asset_id'] == "1.3.0"):
					blocktime = get_block_date(his['block_num'])
					new_order = ITEMS.create(
						from_account = acc.name,
						amount = his['op'][1]['amount']['amount'],
						asset = "CWD",
						op_id = int_op_id,
						deposit_status = 0,
						blocktime = blocktime
					)

					new_order.save()
					stm(dedent("""\
						Новый платёж %s
						Дата и время: %s (GMT)
						Аккаунт %s перевёл %s %s.
						""" % ( str(new_order.op_id), 
								str(new_order.blocktime), 
								new_order.from_account, 
								str(int(new_order.amount)/100000), 
								new_order.asset
							) 
							)
						)
					amount = int(new_order.amount)/100000
					if amount >= config.LIMITS[bot.bc_login]:
						pay_ref(new_order.op_id, blocktime, acc.name, amount, bot.bc_login)
					else:
						if amount>2.5:
							stm("%s Сумма оплаты %s CWD меньше суммы нижнего лимита %s CWD! Автовозврат!" % ( str(new_order.op_id), 
										str(amount), 
										str(config.LIMITS[bot.bc_login])
									)
								)
							cwd.transfer(acc.name, amount-2.5, "CWD", "Возврат! Минимальная сумма оплаты составляет %s CWD" % config.LIMITS[bot.bc_login], account=bot.bc_login)
						else:
							stm("%s Сумма оплаты %s CWD меньше суммы нижнего лимита %s CWD! Сумма меньше, чем размер комиссии. Свяжитесь с клиентом!" % ( str(new_order.op_id), 
										str(amount), 
										str(config.LIMITS[bot.bc_login])
									)
								)							
				else:
					stm(dedent("""\
						!!! НЕСТАНДАРТНЫЙ ПЕРЕВОД ОТ АККАУНТА %s
						ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО ОПЕРАТОРА !!!
						""" % acc.name
							)
						)
	bot.most_recent_op = max_op_id
	bot.save()

if __name__ == "__main__":
	stm("SERVER STARTED")
	try:
		bot_acc = BOT.get(BOT.bc_login == config.GENERAL['bc_login'])
	except:
		acc = Account(config.GENERAL['bc_login'], blockchain_instance = cwd)
		ws.send('{"jsonrpc": "2.0", "method": "get_objects" "params": [["%s"]], "id": 1}' % acc.get("statistics"))
		result = ws.recv()
		ws.send('{"jsonrpc": "2.0", "method": "get_objects" "params": [["%s"]], "id": 1}' % json.loads(result).get('result')[0]['most_recent_op'])
		result = ws.recv()
		most_recent_op = int(json.loads(result).get('result')[0]['operation_id'].split('.')[2])
		bot_acc = BOT.create()
		bot_acc.bc_login = config.GENERAL['bc_login']
		bot_acc.bc_id = acc['id']
		bot_acc.statistics_id = acc.get("statistics")
		bot_acc.most_recent_op = most_recent_op
		bot_acc.save()

	while True:
		for bot in BOT.select():
			get_new_operations(bot)
		time.sleep(30)