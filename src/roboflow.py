

def init():
	from inference_sdk import InferenceHTTPClient

	CLIENT = InferenceHTTPClient(
		# api_url="http://localhost:9001",
		api_url="https://detect.roboflow.com",
		api_key=os.environ['INFERENCE_API_KEY']
	)

	return CLIENT