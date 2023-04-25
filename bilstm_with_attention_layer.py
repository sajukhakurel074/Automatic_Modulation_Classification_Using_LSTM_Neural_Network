# -*- coding: utf-8 -*-
"""BiLSTM_With_Attention.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1_ch3_OmzHlJJvIovDjxsnC7cJyFoR6sL
"""

! sudo apt-get install texlive-latex-recommended 
!sudo apt install cm-super dvipng texlive-latex-extra texlive-latex-recommended

import numpy as np
import pandas as pd
import tensorflow as tf

from tensorflow import keras
from tensorflow.keras import layers
from keras.layers import Input, LSTM
from tensorflow.keras import backend as K

import matplotlib.pyplot as plt
import matplotlib
import pickle
import seaborn as sn

matplotlib.rcParams.update({
    "pgf.texsystem": "pdflatex",
    'font.family': 'serif',
    'text.usetex': True,
    'pgf.rcfonts': False,
})
matplotlib.rcParams['text.latex.unicode']=True

# Commented out IPython magic to ensure Python compatibility.
# %tensorflow_version 2.x
import tensorflow as tf
print("Tensorflow version " + tf.__version__)
try:
  tpu = tf.distribute.cluster_resolver.TPUClusterResolver()  # TPU detection
  print('Running on TPU ', tpu.cluster_spec().as_dict()['worker'])
except ValueError:
  raise BaseException('ERROR: Not connected to a TPU runtime; please see the previous cell in this notebook for instructions!')
tf.config.experimental_connect_to_cluster(tpu)
tf.tpu.experimental.initialize_tpu_system(tpu)
tpu_strategy = tf.distribute.experimental.TPUStrategy(tpu)

from google.colab import drive
drive.mount('/content/drive')

Xd = pd.read_pickle("/content/drive/MyDrive/RML2016.10a_dict.pkl")

# Partition the data
#  into training and test sets of the form we can train/test on 
#  while keeping SNR and Mod labels handy for each
np.random.seed(2016)
n_examples = X.shape[0]
n_train = int(n_examples * 0.6)
train_idx = np.random.choice(range(0,n_examples), size=n_train, replace=False)
test_idx = list(set(range(0,n_examples))-set(train_idx))
X_train = X[train_idx]
X_test =  X[test_idx]
def to_onehot(yy):
    yy1 = np.zeros([len(yy), max(yy)+1])
    yy1[np.arange(len(yy)),yy] = 1
    return yy1
Y_train = to_onehot(list(map(lambda x: mods.index(lbl[x][0]), train_idx)))
Y_test = to_onehot(list(map(lambda x: mods.index(lbl[x][0]), test_idx)))

# Load the dataset ...
#  You will need to seperately download or generate this file

snrs,mods = map(lambda j: sorted(list(set(map(lambda x: x[j], Xd.keys())))), [1,0])
X = []  
lbl = []
for mod in mods:
    for snr in snrs:
        X.append(Xd[(mod,snr)])
        for i in range(Xd[(mod,snr)].shape[0]):  lbl.append((mod,snr))
X = np.vstack(X)

np.random.seed(2016)
n_examples = X.shape[0]
n_train = int(n_examples * 0.5)
train_idx = np.random.choice(range(0,n_examples), size=n_train, replace=False)
test_idx = list(set(range(0,n_examples))-set(train_idx))
X_train = X[train_idx]
X_test =  X[test_idx]
def to_onehot(yy):
    yy1 = np.zeros([len(yy), max(yy)+1])
    yy1[np.arange(len(yy)),yy] = 1
    return yy1
Y_train = to_onehot(list(map(lambda x: mods.index(lbl[x][0]), train_idx)))
Y_test = to_onehot(list(map(lambda x: mods.index(lbl[x][0]), test_idx)))

in_shp = list(X_train.shape[1:])
print(X_train.shape, in_shp)
classes = mods

print(X_train.transpose((0,2,1)).shape)

X_train = X_train.transpose((0,2,1))
X_test = X_test.transpose((0,2,1))

class peel_the_layer(tf.keras.layers.Layer): 
      def __init__(self):    
          ##Nothing special to be done here
          super(peel_the_layer, self).__init__()
          
      def build(self, input_shape):
          ##Define the shape of the weights and bias in this layer
          ##This is a 1 unit layer. 
          units=1
          ##last index of the input_shape is the number of dimensions of the prev
          ##RNN layer. last but 1 index is the num of timesteps
          self.w=self.add_weight(name="att_weights", shape=(input_shape[-1], units), initializer="normal") #name property is useful for avoiding RuntimeError: Unable to create link.
          self.b=self.add_weight(name="att_bias", shape=(input_shape[-2], units), initializer="zeros")
          super(peel_the_layer,self).build(input_shape)
          
      def call(self, x):
          ##x is the input tensor..each word that needs to be attended to
          ##Below is the main processing done during training
          ##K is the Keras Backend import
          e = K.tanh(K.dot(x,self.w)+self.b)
          a = K.softmax(e, axis=1)
          output = x*a
          
          ##return the ouputs. 'a' is the set of attention weights
          ##the second variable is the 'attention adjusted o/p state' or context
          return K.sum(output, axis=1)

inputs = Input(shape=(None, 128, 2))

with tpu_strategy.scope(): # creating the model in the TPUStrategy scope means we will train the model on the TPU
  model = keras.Sequential()
  model.add(layers.Bidirectional(LSTM(32, return_sequences=True)))
  model.add(layers.Bidirectional(LSTM(32, return_sequences=True)))
  model.add(layers.Bidirectional(LSTM(32, return_sequences=True)))
  model.add(peel_the_layer())
  #sum = layer.Concatenate()
  model.add(layers.Dense(32, activation="relu"))
  model.add(layers.Dense(32, activation="relu"))
  model.add(layers.Dense(32, activation="relu"))

  model.add(layers.Dense(11, activation="softmax"))

  model.build((None,128,2))
  model.compile(optimizer='Adam', loss='categorical_crossentropy', metrics=["accuracy"])
  model.summary()

filepath = 'BiLSTM.wts.h5'
nb_epoch = 100     # number of epochs to train on
batch_size = 1024  # training batch size
history = model.fit(X_train,
    Y_train,
    batch_size=batch_size,
    epochs=nb_epoch,
    #show_accuracy=True,
    verbose=2,
    validation_data=(X_test, Y_test),
    callbacks = [
        keras.callbacks.ModelCheckpoint(filepath, monitor='val_loss', verbose=0, save_best_only=True, mode='auto'),
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, verbose=0, mode='auto')
    ])
# we re-load the best weights once training is finished
model.load_weights(filepath)

filepath = 'BiLSTM.wts.h5'
model.load_weights(filepath)

score = model.evaluate(X_test, Y_test, batch_size=1024)
print(score)

with open('./trainHistoryDict', 'wb') as file_pi:
    pickle.dump(history, file_pi)

textwidth = 6.10356
#figure.set_size_inches(w=textwidth/2.5)

print(history.history["loss"])

matplotlib.pyplot.figure(figsize=(textwidth-0.2,3.8), dpi=600)
plt.figure()
plt.plot(history.epoch,history.history['loss'], label='train loss+error')
plt.savefig("/content/sample_data/Test.png")
#plt.xticks(epochs)
plt.show()

matplotlib.pyplot.figure(figsize=(textwidth-0.2,3.8), dpi=600)
plt.title('Training performance')
plt.plot(history.epoch,history.history['loss'], linestyle="dashed", color="black", label='Training Loss')
plt.plot(history.epoch,history.history['val_loss'], color="black", label="Validation Error")
plt.xlabel("Epochs")
plt.ylabel("Loss")
plt.legend()
plt.savefig("BiLSTM_Train_Validation_Loss.png", bbox_inches="tight")
plt.show()

test_Y_hat = model.predict(X_test, batch_size=batch_size)



import time
start = time.perf_counter()
test_Y_hat = model.predict(X_test, batch_size=1024)
end = time.perf_counter()
avg_time = (end - start)/X_test.shape[0]
print("Number of signals: " + str(X_test.shape[0]) )
print("Average time per perdiction: " + str(avg_time * 1e3))
print("Total Time taken: " + str(end-start))

conf = np.zeros([len(classes),len(classes)])
confnorm = np.zeros([len(classes),len(classes)])
for i in range(0,X_test.shape[0]):
    j = list(Y_test[i,:]).index(1)
    k = int(np.argmax(test_Y_hat[i,:]))
    conf[k,j] = conf[k,j] + 1
for i in range(0,len(classes)):
    confnorm[:,i] = conf[:,i] / np.sum(conf[:,i])

print(X_test.shape)
#plt.figure(figsize=(7, 7), dpi=80)
matplotlib.pyplot.figure(figsize=(textwidth-0.2,textwidth-0.2), dpi=600)
sn.set(rc={'figure.figsize':(textwidth,3.8), 'text.usetex' : True })
sn.set(font_scale=0.5) # for label size
ax = sn.heatmap(confnorm, annot=True, cmap="Greens", xticklabels=classes, yticklabels=classes, linewidths=0.5, cbar=False)
ax.set_xticklabels(classes,rotation=45)
ax.set_xlabel("Actual Modulation Type", fontsize="8")
ax.set_ylabel("Predicted Modulation Type", fontsize="8")
ax.set_title("Overall Confusion Matrix", fontsize="12")
#plot_confusion_matrix(confnorm, labels=classes)
fig = ax.get_figure()
fig.savefig("ALSTM_Overall_CM.png", bbox_inches="tight")

def plot_small_confusion(title, data, classes, filename="" ):
  matplotlib.pyplot.figure(figsize=(textwidth/2.3,textwidth/2.3), dpi=600)
  sn.set(rc={'figure.figsize':(textwidth,3.8), 'text.usetex' : True })
  sn.set(font_scale=0.3) # for label size
  ax = sn.heatmap(confnorm, annot=False, cmap="Greens", xticklabels=classes, yticklabels=classes, linewidths=0.5, cbar=False)
  ax.set_xticklabels(classes,rotation=45)
  #ax.set_xlabel("Actual Modulation Type", fontsize="8")
  #ax.set_ylabel("Predicted Modulation Type", fontsize="8")
  ax.set_title(title, fontsize="12")
  #plot_confusion_matrix(confnorm, labels=classes)
  fig = ax.get_figure()
  fig.savefig(filename, bbox_inches="tight")

acc = {}
test_SNRs = np.array( list(map(lambda x: lbl[x][1], test_idx) ) )
accuracies = list()
for snr in snrs:

    # extract classes @ SNR
    #print(np.where(np.array(test_SNRs))==snr)
    #test_X_i = X_test[np.where(np.array(test_SNRs)==snr)]
    #test_Y_i = Y_test[np.where(np.array(test_SNRs)==snr)]    
    test_X_i = X_test[np.nonzero(test_SNRs == snr)]
    test_Y_i = Y_test[np.nonzero(test_SNRs == snr)]
    #test_X_i = np.expand_dims( test_X_i, axis = 1 )
    if ( test_X_i.shape[0] == 0 ):
      continue
    # estimate classes
    test_Y_i_hat = model.predict(test_X_i, batch_size = 1024 )
    conf = np.zeros([len(classes),len(classes)])
    confnorm = np.zeros([len(classes),len(classes)])
    for i in range(0,test_X_i.shape[0]):
        j = list(test_Y_i[i,:]).index(1)
        k = int(np.argmax(test_Y_i_hat[i,:]))
        conf[k,j] = conf[k,j] + 1
    for i in range(0,len(classes)):
        confnorm[:,i] = conf[:,i] / np.sum(conf[:,i])
    #plt.figure()
    #plot_confusion_matrix(confnorm, labels=classes, title="ConvNet Confusion Matrix (SNR=%d)"%(snr))
    plot_small_confusion("Confusion matrix for SNR="+str(snr), confnorm, classes,"BiLSTM_CM_" + str(snr) + ".png")
    cor = np.sum(np.diag(conf))
    ncor = np.sum(conf) - cor
    accur = cor / ( cor + ncor )
    print("Overall Accuracy: ", accur)
    acc[snr] = 1.0*cor/(cor+ncor)
    accuracies.append(accur)
    #plt.plot(snr, cor/(cor+ncor))

#sn.set(font_scale=1.0) # for label size

#plt.style.use("default")

#fig = plt.figure()
matplotlib.pyplot.figure(figsize=(textwidth-0.2,3.8), dpi=600)
#fig.patch.set_facecolor("white")

plt.title('SNR-Accuracy Plot', fontsize="12")
ax = plt.plot(snrs,accuracies, color="black")
plt.grid(b=False)
plt.xlabel("SNR (dB)")
plt.ylabel("Accuracy")
plt.savefig("BiLSTM_SNR_Acc.png", bbox_inches="tight")
plt.show()

plt.figure()
plt.title('Training performance')
plt.plot(history.epoch, history.history['loss'], label='train loss+error')
plt.plot(history.epoch, history.history['val_loss'], label='val_error')
plt.legend()

def plot_confusion_matrix(cm, title='Confusion matrix', cmap=plt.cm.Blues, labels=[]):
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)
    plt.colorbar()
    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=45)
    plt.yticks(tick_marks, labels)
    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')

print(X_test.shape)
test_Y_hat = model.predict(X_test, batch_size=batch_size)
conf = np.zeros([len(classes),len(classes)])
confnorm = np.zeros([len(classes),len(classes)])
for i in range(0,X_test.shape[0]):
    j = list(Y_test[i,:]).index(1)
    k = int(np.argmax(test_Y_hat[i,:]))
    conf[j,k] = conf[j,k] + 1
for i in range(0,len(classes)):
    confnorm[i,:] = conf[i,:] / np.sum(conf[i,:])
plt.figure(figsize=(7, 7), dpi=80)

plot_confusion_matrix(confnorm, labels=classes)

acc = {}
test_SNRs = np.array( list(map(lambda x: lbl[x][1], test_idx) ) )
for snr in snrs:

    # extract classes @ SNR
    #print(np.where(np.array(test_SNRs))==snr)
    #test_X_i = X_test[np.where(np.array(test_SNRs)==snr)]
    #test_Y_i = Y_test[np.where(np.array(test_SNRs)==snr)]    
    test_X_i = X_test[np.nonzero(test_SNRs == snr)]
    test_Y_i = Y_test[np.nonzero(test_SNRs == snr)]
    #test_X_i = np.expand_dims( test_X_i, axis = 1 )
    if ( test_X_i.shape[0] == 0 ):
      continue
    # estimate classes
    test_Y_i_hat = model.predict(test_X_i, batch_size = 1024 )
    conf = np.zeros([len(classes),len(classes)])
    confnorm = np.zeros([len(classes),len(classes)])
    for i in range(0,test_X_i.shape[0]):
        j = list(test_Y_i[i,:]).index(1)
        k = int(np.argmax(test_Y_i_hat[i,:]))
        conf[j,k] = conf[j,k] + 1
    for i in range(0,len(classes)):
        confnorm[i,:] = conf[i,:] / np.sum(conf[i,:])
    plt.figure()
    plot_confusion_matrix(confnorm, labels=classes, title="ConvNet Confusion Matrix (SNR=%d)"%(snr))
    
    cor = np.sum(np.diag(conf))
    ncor = np.sum(conf) - cor
    print("Overall Accuracy: ", cor / (cor+ncor))
    acc[snr] = 1.0*cor/(cor+ncor)