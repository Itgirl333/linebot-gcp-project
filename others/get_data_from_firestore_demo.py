from google.cloud import firestore
db = firestore.Client()
doc_ref = db.collection(u'user_test').document(u'Ada')
doc = doc_ref.get()
if doc.exists:
    print(f'Document data: {doc.to_dict()}')
else:
    print(u'No such document!')
doc.to_dict()