#!/usr/bin/env python3
import glob
import sys, os, time
import subprocess
import re
import time, json, subprocess
from pathlib import Path
import requests
import fire
from functools import cmp_to_key
from utils import *


_camera_id = 0



def main(path, lookback=5, speak=True, prompt='', CHATGPT=False, ROBOFLOW=False, camera_id=0, localization=False, gui=True, notify=True):
	global _camera_id
	_camera_id = camera_id

	if ROBOFLOW:
		from roboflow import init
		CLIENT = init()
	elif CHATGPT:
		from oai import oai

	def create_window():

		title = f'KOOMVCR{time.time()}'

		# create an empty window, sized to the screen resolution - 200 but not fullscreen
		pygame.display.set_mode((pygame.display.Info().current_w - 400, pygame.display.Info().current_h - 200))
		# pygame.display.set_mode((1000, 700))
		pygame.display.set_caption(title)
		pygame.display.flip()

		# get the window id
		time.sleep(1)
		window_id = subprocess.check_output(['xwininfo', '-name', title]).decode()
		window_id = re.search('Window id: (0x[0-9a-f]+)', window_id).group(1)

		print(f'Window id: {window_id}')

		return window_id

	seen = []

	if gui:
		pygame.init()
		w = create_window()

	allfiles = {}

	while True:

		for f in glob.glob(path, recursive=True):
			f = Path(f)
			if f.is_file():
				if str(f) not in allfiles:
					# print('found new file: ' + str(f))
					allfiles[str(f)] = (f.parent, f.stat().st_ctime)

		#print('allfiles:', allfiles)

		# print('sort by ctime...')
		# allfiles.sort(key=lambda python_sucks: python_sucks[0])
		hh = sorted(allfiles.items(), key=lambda x: x[1][1])
		hh = sorted(hh, key=cmp_to_key(picsort))
		print('sorted')
		for i in hh:
			print(i[0], ctime_to_human(i[1][1]))

		allfiles = dict(hh)
		# print('len(allfiles):', len(allfiles))

		# print('play..')

		all = list(allfiles.keys())
		tail = all[-1000:]

		if lookback < 1:
			raise Exception('lookback must be > 0')
		latest = all[-lookback:]
		latest_imgs = [f for f in tail if is_img(f)]

		mqtt_pub('loop', 1)

		latests = [f for f in latest if f not in seen]

		if ROBOFLOW or CHATGPT:
			if len(latests):
				print('sleep to accumulate more images ..')
				time.sleep(5)

		for f in latests:

			seen.append(f)

			print(f'File: {f}')

			if notify:
				subprocess.Popen(
					'notify-send --expire-time=3000 -i /usr/share/icons/gnome/48x48/status/dialog-information.png "Playing" "' + f + '"',
					shell=True)
			if gui:
				# print(f'play file: {f}')
				if False:#is_img(f):
					cmd = f'MPLAYER_VERBOSE=-1 mplayer -vo x11 -msglevel all=0 -noautosub -wid {w} "{f}"'
				else:
					# cmd = f'mpv --really-quiet --wid={w} "{f}"'
					cmd = f'mpv --vo=x11 --wid={w} "{f}"'
				print(cmd)

				if is_img(f):
					print('popen')
					subprocess.Popen(cmd, shell=True)
				else:
					print('call')
					subprocess.call(cmd, shell=True)

			# did we indicate (through espeak) that we found/processed the image
			indicated = False
			inference_service_used = False

			mqtt_pub('motion', 1)

			if len(latest_imgs) and (f is latest_imgs[-1]):

				if ROBOFLOW or CHATGPT:
					inference_service_used = True

				if ROBOFLOW:

					inference = None
					try:
						# tried:
						# fall-detection-real/2
						# human-fall/2
						inference = CLIENT.infer(f, model_id="fall_detection-vjdfb/2")
					except requests.exceptions.ConnectionError:
						subprocess.check_call(['espeak', 'connection error!'])
					except Exception as e:
						subprocess.check_call(['espeak', e])

					if inference:

						# print(json.dumps(inference, indent=2))
						for pr in inference.get('predictions', []):
							x = f'class {pr["class"]} {round(pr["confidence"] * 100)}'
							print(x)
							subprocess.check_call(['espeak', x])
							indicated = True

				if CHATGPT:
					print('chatgpt')

					try:
						reel = []
						if len(latest_imgs) > 9:
							reel.append(latest_imgs[-9])
						if len(latest_imgs) > 5:
							reel.append(latest_imgs[-5])
						elif len(latest_imgs) > 2:
							reel.append(latest_imgs[-2])
						reel.append(f)

						print('reel:', reel)

						reply = oai(reel, prompt)
						emergency = reply.get('emergency')
					except Exception as e:
						print(e)
						subprocess.check_call(['espeak', f'Error: {e}'])
					else:
						print('emergency:', emergency.__repr__())
						mqtt_pub('chatgpt/emergency', 0 if emergency == 'none' else 1)
						description = reply.get("image_contents")
						description_localized = reply.get("image_contents_localized")
						if emergency != "none":
							mqtt_pub('chatgpt/description', description)
							indicated = True

						if speak:
							subprocess.check_call(['espeak', f'Emergency: {emergency}'])
							if localization:
								subprocess.check_call(['espeak', '-v', 'czech', f'Popis: {description_localized}'])
							else:
								subprocess.check_call(['espeak', f'Description: {description}'])
						subprocess.check_call(['espeak', f'Explanation: {reply.get("explanation")}'])

			if not indicated and speak:
				subprocess.check_call(['espeak', 'motion!'])

			if inference_service_used:
				sleep_remaining_secs = 60
				while sleep_remaining_secs > 0:
					print(f'sleeping... {sleep_remaining_secs}')
					time.sleep(1)
					sleep_remaining_secs -= 1

		time.sleep(0.1)
		print('---')


hostname = subprocess.check_output(['hostname']).decode().strip()


def mqtt_pub(topic, value):
	topic = hostname + str(_camera_id) + '/' + topic + '/state'
	h = os.environ.get('MQTT_HOST', None)
	if h is None:
		print('MQTT_HOST not set')
		return
	p = int(os.environ.get('MQTT_PORT', 1883))
	import paho.mqtt.publish as publish
	auth = {}
	if os.environ.get('MQTT_USER', None):
		auth['username'] = os.environ.get('MQTT_USER')
	if os.environ.get('MQTT_PASS', None):
		auth['password'] = os.environ.get('MQTT_PASS')
	try:
		publish.single(topic, str(value), hostname=h, port=p, auth=auth, qos=1, retain=True)
	except Exception as e:
		print(e)
	else:
		print(f'Published {value} to {topic} on {h}:{p}')


def is_img(f):
	return any([f.lower().endswith(ext) for ext in 'jpg;webp;avif;jpeg;png'.split(';')])

if __name__ == '__main__':
	fire.Fire(main)
