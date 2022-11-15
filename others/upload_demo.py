from google.cloud import storage
# 建立跟cloud storage 溝通的客戶端
storage_client = storage.Client()
# 桶子, 物件, 本地檔案事先指定好
bucket_name="linebot-tibame01-storage"
# 上傳到桶子之後的名稱
destination_blob_name="cxcxc.txt"
# 本地要上傳的檔案名稱
source_file_name="requirements.txt"
# 正式上傳檔案至bucket內
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(destination_blob_name)
blob.upload_from_filename(source_file_name)