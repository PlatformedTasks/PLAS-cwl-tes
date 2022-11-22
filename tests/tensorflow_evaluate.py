import tensorflow as tf
from tensorflow import keras
import tarfile
import sys


def untarfile(tar_file):
    tar = tarfile.open(tar_file)
    tar.extractall()
    tar.close()


untarfile(sys.argv[1])
reconstructed_model = keras.models.load_model('my_model')

_, (mnist_images, mnist_labels) = \
    tf.keras.datasets.mnist.load_data(path='mnist.npz')

dataset = tf.data.Dataset.from_tensor_slices(
    (tf.cast(mnist_images[..., tf.newaxis] / 255.0, tf.float32),
     tf.cast(mnist_labels, tf.int64))
)

dataset = dataset.repeat().shuffle(10000).batch(128)

print("Evaluate model on test data")
results = reconstructed_model.evaluate(dataset, steps=10, return_dict=True)

print(results)



