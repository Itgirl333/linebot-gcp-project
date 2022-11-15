from google.cloud import storage
storage_client = storage.Client()
bucket_name="linebot-tibame01-storage"
blob_name="cxcxc.txt"
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(blob_name)
blob.delete()