# modified from pytorch densenet
# so it runs with my script
# NOTE: WIP

import tensorflow as tf

class DenseLayerTF(tf.keras.layers.Layer):
  # NOTE: haven't implemented memory efficient style, see pytorch vision
  def __init__(self,
               num_input_features,
               growth_rate,
               bn_size,
               drop_rate,
               data_format='channels_first'):
    super(DenseLayerTF, self).__init__()
    self.bn_axis = 1 if data_format == 'channels_first' else -1
    self.relu = tf.keras.layers.ReLU()
    self.dropout = tf.keras.layers.Dropout(drop_rate)

    # 1x1 Conv
    self.norm1 = tf.keras.layers.BatchNormalization(axis=self.bn_axis)
    self.conv1 = tf.keras.layers.Conv2D(bn_size * growth_rate, 1, 1, data_format=data_format, use_bias=False)
    
    # 3x3 Conv
    self.norm2 = tf.keras.layers.BatchNormalization(axis=self.bn_axis)
    self.padd2 = tf.keras.layers.ZeroPadding2D(padding=1, data_format=data_format)
    self.conv2 = tf.keras.layers.Conv2D(growth_rate, 3, 1, data_format=data_format)
  
  def call(self, inputs):
    x = self.norm1(inputs)
    x = self.relu(x)
    x = self.conv1(x)
    x = self.norm2(x)
    x = self.relu(x)
    x = self.padd2(x)
    x = self.conv2(x)
    x = self.dropout(x)
    return x


class DenseBlockTF(tf.keras.layers.Layer):
  def __init__(self, 
               num_layers, 
               num_input_features, 
               bn_size, 
               growth_rate,
               drop_rate,
               data_format='channels_first'):
    super(DenseBlockTF, self).__init__()
    self.layers = []
    self.concat_axis = 1 if data_format == 'channels_first' else -1
    for i in range(num_layers):
      layer = DenseLayerTF(
        num_input_features + i * growth_rate,
        growth_rate=growth_rate,
        bn_size=bn_size,
        drop_rate=drop_rate,
        data_format=data_format
      )
      self.layers.append(layer)
  
  def call(self, inputs):
    concat_feat=inputs
    for i in range(len(self.layers)):
      x = self.layers[i](concat_feat)
      concat_feat = tf.concat([concat_feat, x], self.concat_axis)
    return concat_feat
    

class TransitionBlockTF(tf.keras.layers.Layer):
  def __init__(self, num_output_features, data_format='channels_first'):
    super(TransitionBlockTF, self).__init__()
    self.bn_axis = 1 if data_format == 'channels_first' else -1
    self.norm = tf.keras.layers.BatchNormalization(axis=self.bn_axis)
    self.relu = tf.keras.layers.ReLU()
    self.conv = tf.keras.layers.Conv2D(num_output_features, 1, 1, use_bias=False, data_format=data_format)
    self.pool = tf.keras.layers.AvgPool2D(2, 2, data_format=data_format)
  
  def call(self, inputs):
    x = self.norm(inputs)
    x = self.relu(x)
    x = self.conv(x)
    x = self.pool(x)
    return x


class DenseNetTF(tf.keras.Model):
  def __init__(self, name, classes=10, is_training=True,
               initial_features=16, initial_kernel_size=3, initial_stride = 1,
               blocks_config=None, growth_rate=12, drop_rate=.0, bn_size=4, 
               weights=None, data_format='channels_first', input_shape=None):

    super(DenseNetTF, self).__init__(name='densenet'+name)
    self.bn_axis = 1 if data_format == 'channels_first' else -1
    self.num_classes = classes
    self.features = tf.keras.Sequential()
    if len(blocks_config) > 3:
      # bigger densenet
      self.features.add(tf.keras.layers.ZeroPadding2D(padding=3, data_format=data_format, name='feature_zero_pad', input_shape=input_shape))
      self.features.add(tf.keras.layers.Conv2D(initial_features, initial_kernel_size, initial_stride, data_format=data_format, use_bias=False, kernel_initializer='he_normal', name='conv1'))
      self.features.add(tf.keras.layers.BatchNormalization(axis=self.bn_axis))
      self.features.add(tf.keras.layers.ReLU())
      self.features.add(tf.keras.layers.ZeroPadding2D(padding=1, data_format=data_format, name='pool1_zero_pad'))
      self.features.add(tf.keras.layers.MaxPool2D(pool_size=3, strides=2, padding='same', data_format=data_format))
    else:
      # smaller densenet, e.g. for cifar10
      self.features.add(tf.keras.layers.Conv2D(initial_features, initial_kernel_size, initial_stride, 'same', data_format=data_format, use_bias=False, kernel_initializer='he_normal', input_shape=input_shape))
      
    # Dense blocks
    num_features = initial_features
    for i, num_layers in enumerate(blocks_config):
      dblock = DenseBlockTF(
        num_layers=num_layers,
        num_input_features=num_features,
        bn_size=bn_size,
        growth_rate=growth_rate,
        drop_rate=drop_rate,
        data_format=data_format
      )
      self.features.add(dblock)
      
      num_features = num_features + num_layers * growth_rate

      # add transition layers
      if i != len(blocks_config) - 1:
        trans_layer = TransitionBlockTF(num_features // 2, data_format=data_format)
        num_features = num_features // 2
    
    # final batch norm
    self.features.add(tf.keras.layers.BatchNormalization(axis=self.bn_axis))

    # activation
    self.features.add(tf.keras.layers.ReLU())

    # avg pool
    self.features.add(tf.keras.layers.GlobalAvgPool2D(data_format))

    # Linear layer
    self.classifier = tf.keras.layers.Dense(classes, activation='softmax')
  
  def call(self, inputs):
    x = self.features(inputs['image'])
    x = self.classifier(x)
    # NOTE: not logits
    return x

#NOTE: haven't done any loading weights, save weights
def densenet121(**kwargs):
  return DenseNetTF('121', blocks_config=(6,12,24,16), growth_rate=32, initial_features=64, **kwargs)

def densenet40(**kwargs):
  return DenseNetTF('40', blocks_config=(12,12,12), growth_rate=12, initial_features=16, **kwargs)
