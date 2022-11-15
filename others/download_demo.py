from google.cloud import storage
# 建立客戶端
storage_client = storage.Client()
# 指定桶子名
bucket_name="linebot-tibame01-storage"
# 告知遠端物件的名字
source_blob_name="cxcxc.txt"
# 下載回本地端的名字
destination_file_name="test.txt"
# 建立bucket客戶端
bucket = storage_client.bucket(bucket_name)
# 建立遠端物件的客戶端
blob = bucket.blob(source_blob_name)
blob.download_to_filename(destination_file_name)