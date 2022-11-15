from google.cloud import firestore
db = firestore.Client()
db.collection(u'user_test').document(u'Ada').delete()