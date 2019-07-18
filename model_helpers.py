import tensorflow as tf
import keras.backend as K
import numpy as np

from keras.models import Model
from keras.layers import Input, Conv2D, Lambda, UpSampling2D, ELU


"""
Model parameters from the original paper: https://arxiv.org/pdf/1811.06861.pdf 
"""
input_shape = (128, 128, 1)

original_conv_layer_datas = [
    {'kernel_size': 5, 'dilation_rate': 1, 'strides': 1, 'filters': 32},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 64},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 64},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 2, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 2, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 4, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 8, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 16, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 128},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 64},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 64},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 32},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 16},
    {'kernel_size': 3, 'dilation_rate': 1, 'strides': 1, 'filters': 1}
]


def conv_block(outputs, kernel, dilation, strides, filters, model_width):
    outputs = Lambda(
        lambda x: tf.pad(x, [[0, 0], [dilation, dilation], [dilation, dilation], [0, 0]], 'REFLECT'))(outputs)
    outputs = Conv2D(filters=filters * model_width, kernel_size=kernel, strides=strides, padding='valid',
                     dilation_rate=dilation, activation='linear')(outputs)
    return ELU()(outputs)


def create_anomaly_cnn(input_shape=input_shape, conv_layer_datas=None, model_width=1):
    """
    Creates the CNN used for Anomaly Detection.
    :param input_shape: The shape of the inputed image
    :param conv_layer_datas: The layer parameters of the model
    :param model_width: Determines the rate to which factor the number of filter will be increased
    :return: Returns the model
    """
    conv_layer_datas = conv_layer_datas if conv_layer_datas else original_conv_layer_datas

    assert len(input_shape) == 2 or input_shape[-1] == 1, 'Images must only have one channel (grayscale)!'
    inputs = Input(shape=(*input_shape[:2], 1))
    outputs = inputs
    for i, data in enumerate(conv_layer_datas):
        outputs = conv_block(outputs, data['kernel_size'], data['dilation_rate'], data['strides'], data['filters'],
                             model_width if i != len(conv_layer_datas) - 1 else 1)
        outputs = UpSampling2D(size=2)(outputs) if i == 11 else outputs
    outputs = Lambda(lambda x: tf.pad(x, [[0, 0], [1, 1], [1, 1], [0, 0]], 'REFLECT'))(outputs)
    outputs = Lambda(lambda x: K.clip(x, -1, 1), name='clip')(outputs)

    return Model(inputs=inputs, outputs=outputs)


def create_center_mask(img, center_size):
    mask = np.zeros_like(img)
    h, w = img.shape[:2]
    y_start = h // 2 - center_size[0] // 2
    x_start = w // 2 - center_size[1] // 2
    mask[y_start:y_start + center_size[0], x_start:x_start + center_size[1]] = 1

    return mask


def l1_matrix_norm(M):
    return K.cast(K.max(K.sum(K.abs(M), axis=0)), 'float64')


def reconstruction_loss(img, mask=None, center_size=None, center_weight=0.9):
    assert mask or center_size, 'You have to either specify the mask or the center_size'
    mask = mask if mask else create_center_mask(img, center_size[:2])
    mask_inv = 1 - mask

    def loss(y_true, y_pred):
        return (center_weight * l1_matrix_norm(mask * (y_true - (mask_inv * y_pred))) + (1 - center_weight) * l1_matrix_norm(mask_inv * (y_true - (mask_inv * y_pred)))) / np.prod(y_true.shape[:2])

    return loss

