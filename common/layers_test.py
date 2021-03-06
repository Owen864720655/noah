'''
Created on Aug 26, 2016

@author: lxh5147
'''
import unittest
from layers import BiDirectionalLayer, MLPClassifierLayer, AttentionLayer, RNNDecoderLayerBase, RNNDecoderLayer, RNNDecoderLayerWithBeamSearch
import numpy as np
import keras.backend as K
from keras.layers import Dense, Input, GRU, Embedding

np.random.seed(20080524)

class LayersTest(unittest.TestCase):
    def test_BiDirectionalLayer(self):
        layer = BiDirectionalLayer(time_step_axis = 1)
        # test config
        self.assertEqual(layer.get_config(), BiDirectionalLayer.from_config(layer.get_config()).get_config(), "config")

        left_to_right = Input((None, 3))
        right_to_left = Input((None, 2))
        output = layer([left_to_right, right_to_left])
        # check keras shape
        self.assertEqual(output._keras_shape, (None, None, 5), "_keras_shape")
        # check with call
        f = K.function(inputs = [left_to_right, right_to_left ], outputs = [output])
        left_to_right_val = [[[1, 2, 3], [4, 5, 6]], [[7, 8, 9], [10, 11, 12]]]
        right_to_left_val = [[[0.1, 0.2], [0.4, 0.5]], [[0.7, 0.8], [1.0, 1.1]]]
        output_val_ref = [[[1, 2, 3, 0.4, 0.5], [4, 5, 6, 0.1, 0.2]], [[7, 8, 9, 1.0, 1.1], [10, 11, 12, 0.7, 0.8]]]
        output_val = f([left_to_right_val, right_to_left_val])[0]
        self.assertTrue(np.sum(np.abs(output_val - output_val_ref)) < 0.0001, 'output_val')

    def test_MLPClassifierLayer(self):
        output_dim = 4
        hidden_unit_numbers = [2, 3, 4]
        hidden_unit_activation_functions = ['relu', 'relu', 'relu']

        output_layer = Dense(output_dim, activation = 'softmax')
        hidden_layers = []
        for hidden_unit_number, hidden_unit_activation_function in zip(hidden_unit_numbers, hidden_unit_activation_functions):
            layer = Dense(hidden_unit_number, activation = hidden_unit_activation_function)
            hidden_layers.append(layer)

        layer = MLPClassifierLayer(output_layer, hidden_layers)
        # test config
        self.assertEqual(layer.get_config(), MLPClassifierLayer.from_config(layer.get_config()).get_config(), "config")

        input_tensor = Input((2,))
        output_tensor = layer(input_tensor)
        self.assertEqual(output_tensor._keras_shape, (None, 4), "_keras_shape")

        f = K.function(inputs = [input_tensor], outputs = [output_tensor])
        input_tensor_value = [[1, 2], [0.1, 0.2]]  # 2 samples
        output_tensor_value = f([input_tensor_value])[0]
        self.assertEqual(output_tensor_value.shape, (2, 4), "output_tensor_value")
        # TODO: check value

    def test_AttentionLayer(self):
        attention_context_dim = 2

        init_W_a = np.array([[1, 2], [3, 4], [5, 6]])  # 3*2
        init_U_a = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])  # 4*2
        init_v_a = np.array([0.1, 0.2])

        layer = AttentionLayer(attention_context_dim = attention_context_dim, weights = [init_W_a, init_U_a, init_v_a])
        # test config
        self.assertEqual(layer.get_config(), AttentionLayer.from_config(layer.get_config()).get_config(), "config")

        s = Input((3,))  # current state tensor
        h = Input((None, 4))  # context
        self.assertEqual(layer([s, h])._keras_shape, (None, 4), "_keras_shape")

        tensors_to_debug = []
        output = AttentionLayer._calc(s, h, K.variable(init_W_a), K.variable(init_U_a), K.variable(init_v_a) , tensors_to_debug = tensors_to_debug)

        # check with call to see detailed computation process
        f = K.function(inputs = [s, h ], outputs = [output] + tensors_to_debug)
        s_val = [[1, 2, 3], [4, 5, 6]]
        h_val = [[[1, 2, 3, 4], [5, 6, 7, 8]], [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]]
        output_val_ref = [[3, 4, 5, 6], [0.3, 0.4, 0.5, 0.6]]
        output_val_list = f([s_val, h_val])
        output_val = output_val_list[0]
        W_U_sum_val = output_val_list[3]
        W_U_sum_val_ref = [[[72., 88.], [136., 168.]], [[54., 70.], [60.4, 78.]]]
        self.assertTrue(np.sum(np.abs(output_val - output_val_ref)) < 0.0001, 'output_val')
        self.assertTrue(np.sum(np.abs(W_U_sum_val - W_U_sum_val_ref)) < 0.0001, 'W_U_sum_val')

    def test_RNNDecoderLayerBase(self):
        rnn_cell_output_dim = 3
        rnn_cell = GRU(output_dim = rnn_cell_output_dim, return_sequences = True)
        attention_context_dim = 2
        attention = AttentionLayer(attention_context_dim = attention_context_dim)

        embedding_dim = 4
        embedding_vac_size = 5
        embedding = Embedding (input_dim = embedding_vac_size, output_dim = embedding_dim)
        layer = RNNDecoderLayerBase(rnn_cell, attention, embedding)
        # test config: should use custom objects for custom layers
        custom_objects = {AttentionLayer.__name__: AttentionLayer}
        self.assertEqual(layer.get_config(), RNNDecoderLayerBase.from_config(layer.get_config(), custom_objects).get_config(), "config")
        # test step: before calling step,build the layer first
        input_x_shape = (None, None)
        context_shape = (None, None, embedding_dim)
        layer.build(input_shapes = [input_x_shape, context_shape])

        x_step = K.placeholder((None, embedding_dim))
        context = K.placeholder((None, None, embedding_dim))
        state = K.placeholder((None, rnn_cell_output_dim))
        constants = rnn_cell.get_constants(K.expand_dims(x_step, 1))
        output, states = layer.step(x_step, [state] + constants , context)
        f = K.function(inputs = [x_step, context, state ], outputs = [output, states[0]])
        x_step_val = [[1, 2, 3, 4], [5, 6, 7, 8]]
        context_val = [[[0.1, 0.2, 0.3, 0.4], [0.3, 0.5, 0.7, 0.2]], [[0.2, 0.1, 0.5, 0.6], [0.4, 0.3, 0.8, 0.1]]]
        state_val = [[1, 2, 3], [0.1, 0.2, 0.3]]
        outputs_val = f([x_step_val, context_val, state_val])
        rnn_cell_output_val = outputs_val[0]
        self.assertEqual(rnn_cell_output_val.shape, (2, rnn_cell_output_dim), "rnn_cell_output_val")
        # TODO: check value

    def test_RNNDecoderLayer(self):
        rnn_cell_output_dim = 3
        rnn_cell = GRU(output_dim = rnn_cell_output_dim, return_sequences = True)
        attention_context_dim = 2
        attention = AttentionLayer(attention_context_dim = attention_context_dim)

        embedding_dim = 4
        embedding_vac_size = 5
        embedding = Embedding (input_dim = embedding_vac_size, output_dim = embedding_dim, weights = [np.array([[0, 0, 0, 0], [1, 2, 3, 4], [5, 6, 7, 8], [9, 1, 3, 4], [8, 7, 4, 2]])])
        layer = RNNDecoderLayer(rnn_cell, attention, embedding)
        # test config: should use custom objects for custom layers
        custom_objects = {AttentionLayer.__name__: AttentionLayer}
        self.assertEqual(layer.get_config(), RNNDecoderLayer.from_config(layer.get_config(), custom_objects).get_config(), "config")

        x = Input((None,), dtype = 'int32')
        context = Input((None, embedding_dim))
        outputs = layer([x, context])
        self.assertEqual(outputs._keras_shape, (None, None, rnn_cell_output_dim), "_keras_shape")
        f = K.function(inputs = [x, context ], outputs = [outputs])
        x_val = [[1, 1, 3, 4], [1, 2, 4, 0]]
        context_val = [[[0.1, 0.2, 0.3, 0.4], [0.3, 0.5, 0.7, 0.2]], [[0.2, 0.1, 0.5, 0.6], [0.4, 0.3, 0.8, 0.1]]]
        output_val = f([x_val, context_val])[0]
        self.assertEqual(output_val.shape, (2, 4, rnn_cell_output_dim), "output_val")
        # TODO: check value

    def test_RNNDecoderLayerWithBeamSearch(self):
        rnn_cell_output_dim = 3
        rnn_cell = GRU(output_dim = rnn_cell_output_dim, return_sequences = True)
        attention_context_dim = 2
        attention = AttentionLayer(attention_context_dim = attention_context_dim)

        embedding_dim = 4
        embedding_vac_size = 5
        embedding = Embedding (input_dim = embedding_vac_size, output_dim = embedding_dim)
        classifier_output_layer = Dense(output_dim = embedding_vac_size, activation = 'softmax')
        hidden_unit_numbers = [2, 3, 4]
        hidden_unit_activation_functions = ['relu', 'relu', 'relu']
        hidden_layers = []
        for hidden_unit_number, hidden_unit_activation_function in zip(hidden_unit_numbers, hidden_unit_activation_functions):
            layer = Dense(hidden_unit_number, activation = hidden_unit_activation_function)
            hidden_layers.append(layer)

        mlp_classifier = MLPClassifierLayer(classifier_output_layer, hidden_layers)
        layer = RNNDecoderLayerWithBeamSearch(mlp_classifier = mlp_classifier, max_output_length = 2, beam_size = 3, rnn_cell = rnn_cell, attention = attention, embedding = embedding)
        # test config: should use custom objects for custom layers
        custom_objects = {AttentionLayer.__name__: AttentionLayer, MLPClassifierLayer.__name__: MLPClassifierLayer}
        self.assertEqual(layer.get_config(), RNNDecoderLayerWithBeamSearch.from_config(layer.get_config(), custom_objects).get_config(), "config")
        initial_input = Input((1,), dtype = 'int32')
        context = Input((None, embedding_dim))
        outputs = layer([initial_input, context])
        f = K.function(inputs = [initial_input, context], outputs = outputs)
        initial_input_val = [[0], [0]]  # two samples
        context_val = [[[0.1, 0.2, 0.3, 0.4], [0.3, 0.5, 0.7, 0.2]], [[0.2, 0.1, 0.5, 0.6], [0.4, 0.3, 0.8, 0.1]]]
        outputs_val = f([initial_input_val, context_val])
        self.assertEqual(outputs_val[0].shape, (layer.max_output_length, 2, layer.beam_size), "output_label_id")
        self.assertEqual(outputs_val[1].shape, (layer.max_output_length, 2, layer.beam_size), "prev_output_index")
        self.assertEqual(outputs_val[2].shape, (layer.max_output_length, 2, layer.beam_size), "output_score")
        # TODO: check value
if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
