import numpy
import time
import tensorflow as tf
from keras.datasets import imdb
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import SimpleRNN
from keras.layers.embeddings import Embedding
from keras.preprocessing import sequence

# fix random seed for reproducibility
numpy.random.seed(7)
# load the dataset but only keep the top n words, zero the rest
top_words = 5000
(X_train, y_train), (X_test, y_test) = imdb.load_data(num_words=top_words)
# truncate and pad input sequences
max_review_length = 500
X_train = sequence.pad_sequences(X_train, maxlen=max_review_length)
X_test = sequence.pad_sequences(X_test, maxlen=max_review_length)




num_words = 15000
maxlen = 130
# create the model
model = Sequential()
model.add(Embedding(num_words, 32, input_length = len(X_train[0])))
model.add(SimpleRNN(16, input_shape=(num_words, maxlen), return_sequences=False, activation="relu"))
model.add(Dense(1, activation='sigmoid'))


model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
print(model.summary())
model.fit(X_train, y_train, epochs=3, batch_size=64)

# Final evaluation of the model
scores = model.evaluate(X_test, y_test, verbose=0)
print("Accuracy: %.2f%%" % (scores[1]*100))

saved_model_dir = 'rnn_imdb'
model.save(saved_model_dir) 


load_model_time = time.time()
model = tf.keras.models.load_model(saved_model_dir)
load_model_time = time.time() - load_model_time
scores = model.evaluate(X_test, y_test, verbose=0)
print("Load model Accuracy: %.2f%%" % (scores[1]*100))
