# -*- coding: utf-8 -*-

"""
Main layer-typed classes
"""

import numpy as np
from abc import ABC, abstractmethod

from activations import (
    ReLU, ReLU_prime,
    leaky_ReLU, leaky_ReLU_prime,
    tanh, tanh_prime,
    softmax, softmax_prime,
    sigmoid, sigmoid_prime
)

from utils import count_nb_decimals_places


##############################################################################


class Layer(ABC):
    """
    Base (abstract) layer class
    """
    def __init__(self):
        self.input  = None
        self.output = None
        self.nb_trainable_params = None
    
    @abstractmethod
    def forward_propagation(self, input_data, training=True):
        """
        Computes the output Y of a layer for a given input X. The `training`
        kwarg indicates whether we're currently in the training phase or not
        (`training` will only be set to `False` during the validation and testing
         phases)
        """
        pass
    
    @abstractmethod
    def backward_propagation(self, output_gradient, learning_rate):
        """
        Computes dE/dX for a given dE/dY, and updates the trainable parameters
        if there are any (using gradient descent)
        """
        pass


##############################################################################


class InputLayer(Layer):
    """
    Input layer. The only purpose of this class is to be the very first layer
    of the network
    """
    def __init__(self, input_size):
        assert input_size > 0
        self.input_size = input_size
        self.nb_trainable_params = 0
    
    def __str__(self):
        return f"{self.__class__.__name__}({self.input_size})"
    
    def forward_propagation(self, input_data, training=True):
        """
        Simply returns the input
        """
        self.input  = input_data
        self.output = self.input
        return self.output
    
    def backward_propagation(self, output_gradient, learning_rate):
        """
        NB : Here, `learning_rate` is not used because there are no trainable
             parameters
        """
        input_gradient = output_gradient
        return input_gradient


##############################################################################


class DenseLayer(Layer):
    """
    Dense (i.e. fully connected) layer
    """
    def __init__(self, nb_neurons, seed=None):
        assert nb_neurons > 0
        self.output_size = nb_neurons
        self.seed = seed
    
    def __str__(self):
        return f"{self.__class__.__name__}({self.output_size})"
    
    def build(self, input_size):
        """
        Now that we know the input size of the layer, we can actually initialize
        the latter. This layer is built when it is added to the network (with
        the `Network.add` method of the `network.py` script)
        """
        assert input_size > 0
        self.input_size = input_size
        
        # using the "He initialization" (because it works well with the ReLU activation)
        np.random.seed(self.seed)
        initial_std = np.sqrt(2.0 / self.input_size)
        self.weights = initial_std * np.random.randn(self.input_size, self.output_size)
        self.biases  = initial_std * np.random.randn(1, self.output_size)
        np.random.seed(None) # resetting the seed
        
        # = self.input_size * self.output_size + self.output_size
        # = (self.input_size + 1) * self.output_size
        self.nb_trainable_params = self.weights.size + self.biases.size
    
    def forward_propagation(self, input_data, training=True):
        """
        Applies the weights and biases to the input, and returns the
        corresponding output
        """
        self.input  = input_data
        
        # duplicating the biases for batch processing
        batch_size = self.input.shape[0]
        duplicated_biases = np.tile(self.biases, (batch_size, 1))
        
        self.output = self.input @ self.weights + duplicated_biases
        return self.output
    
    def backward_propagation(self, output_gradient, learning_rate):
        """
        Computes dE/dW and dE/dB for a given output_gradient=dE/dY, updates
        the weights and biases, and returns the input_gradient=dE/dX
        """
        input_gradient = output_gradient @ self.weights.T # = dE/dX
        
        # gradient averaging for batch processing
        batch_size = output_gradient.shape[0]
        weights_gradient = (1.0 / batch_size) * self.input.T @ output_gradient # = dE/dW
        biases_gradient = np.mean(output_gradient, axis=0, keepdims=True) # = dE/dB
        
        # updating the trainable parameters (using gradient descent)
        self.weights -= learning_rate * weights_gradient
        self.biases  -= learning_rate * biases_gradient
        
        return input_gradient


##############################################################################


class ActivationLayer(Layer):
    """
    Activation layer
    """
    
    # class variable
    AVAILABLE_ACTIVATIONS = {
        "relu"       : (ReLU, ReLU_prime),
        "leaky_relu" : (leaky_ReLU, leaky_ReLU_prime),
        "tanh"       : (tanh, tanh_prime),
        "softmax"    : (softmax, softmax_prime),
        "sigmoid"    : (sigmoid, sigmoid_prime)
    }
    
    def __init__(self, activation_name, **kwargs):
        assert isinstance(activation_name, str)
        activation_name = activation_name.lower()
        if activation_name not in list(ActivationLayer.AVAILABLE_ACTIVATIONS.keys()):
            raise ValueError(f"ActivationLayer.__init__ - Unrecognized activation name : \"{activation_name}\"")
        
        self.activation_name = activation_name
        self.activation, self.activation_prime = ActivationLayer.AVAILABLE_ACTIVATIONS[self.activation_name]
        
        if self.activation_name == "leaky_relu":
            default_leaky_ReLU_coeff = 0.01
            leaky_ReLU_coeff = kwargs.get("leaky_ReLU_coeff", default_leaky_ReLU_coeff)
            assert (leaky_ReLU_coeff > 0) and (leaky_ReLU_coeff < 1)
            self.activation_kwargs = {
                "leaky_ReLU_coeff" : leaky_ReLU_coeff
            }
        else:
            self.activation_kwargs = {}
        
        # NB : Since the softmax activation only applies to VECTORS (and not
        #      scalars), the backpropagation formula won't be the same as the other
        #      activations. Essentially, the element-wise multiplication becomes
        #      an actual matrix multiplication (cf. the `backward_propagation` method)
        self._is_softmax = (self.activation_name == "softmax")
        
        self.nb_trainable_params = 0
    
    def __str__(self):
        if self.activation_name == "leaky_relu":
            leaky_ReLU_coeff = self.activation_kwargs["leaky_ReLU_coeff"]
            precision_leaky_ReLU_coeff = max(2, count_nb_decimals_places(leaky_ReLU_coeff))
            extra_info = f", {leaky_ReLU_coeff:.{precision_leaky_ReLU_coeff}f}"
        else:
            extra_info = ""
        return f"{self.__class__.__name__}(\"{self.activation_name}\"{extra_info})"
    
    def forward_propagation(self, input_data, training=True):
        """
        Returns the activated input
        """
        self.input  = input_data
        self.output = self.activation(self.input, **self.activation_kwargs)
        return self.output
    
    def backward_propagation(self, output_gradient, learning_rate):
        """
        NB : Here, `learning_rate` is not used because there are no trainable
             parameters
        """
        activation_prime_of_input = self.activation_prime(self.input, **self.activation_kwargs)
        
        if not(self._is_softmax):
            # element-wise multiplication
            input_gradient = output_gradient * activation_prime_of_input
        else:
            batch_size = output_gradient.shape[0]
            
            input_gradient = np.zeros(output_gradient.shape, dtype=output_gradient.dtype)
            for batch_sample_index in range(batch_size):
                # matrix multiplication (NOT element-wise multiplication)
                input_gradient[batch_sample_index, :] = output_gradient[batch_sample_index, :] @ activation_prime_of_input[batch_sample_index]
            
            """
            The previous code block is completely equivalent to the following line :
            
            input_gradient = (output_gradient.reshape(batch_size, 1, output_gradient.shape[1]) @ activation_prime_of_input).reshape(output_gradient.shape)
            
            --> Basically, we're using 3D matrix multiplication tricks to make
                the computations a bit more compact !
            """
        
        return input_gradient


##############################################################################


class BatchNormLayer(Layer):
    """
    BatchNorm regularization layer
    """
    def __init__(self):
        # initializing the trainable parameters
        self.gamma = 1.0
        self.beta  = 0.0
        
        self.nb_trainable_params = 2
        
        # initializing the non-trainable parameters
        self.moving_mean = 0.0
        self.moving_var  = 1.0
        self.moving_std  = None
        
        # by default
        self.momentum = 0.99
        
        assert (self.momentum > 0) and (self.momentum < 1)
        
        # by default (used for numerical stability)
        self.epsilon = 1e-4
        
        # initializing the cache
        self.cached_input_data = None
    
    def __str__(self):
        return f"{self.__class__.__name__}()"
    
    def forward_propagation(self, input_data, training=True):
        """
        Returns the normalized (and rescaled) input
        """
        self.input = input_data
        
        if training:
            input_mean = self.input.mean(axis=1, keepdims=True)
            centered_input = self.input - input_mean
            input_variance = self.input.var(axis=1, keepdims=True)
            input_std = np.sqrt(input_variance + self.epsilon)
            normalized_input = centered_input / input_std
            
            # we're caching the input data in order to save some computational
            # time during backpropagation
            self.cached_input_data = (centered_input, input_std, normalized_input)
            
            # updating the non-trainable parameters
            self.moving_mean = self.momentum * self.moving_mean + (1 - self.momentum) * np.mean(input_mean)
            self.moving_var  = self.momentum * self.moving_var  + (1 - self.momentum) * np.mean(input_variance)
        else:
            if self.moving_std is None:
                self.moving_std = np.sqrt(self.moving_var + self.epsilon)
            normalized_input = (self.input - self.moving_mean) / self.moving_std
        
        # rescaling the normalized input
        self.output = self.gamma * normalized_input + self.beta
        
        return self.output
    
    def backward_propagation(self, output_gradient, learning_rate):
        """
        Computes dE/d_gamma and dE/d_beta for a given output_gradient=dE/dY,
        updates gamma and beta, and returns the input_gradient=dE/dX
        """
        centered_input, input_std, normalized_input = self.cached_input_data
        
        output_gradient_mean = output_gradient.mean(axis=1, keepdims=True)
        centered_output_gradient = output_gradient - output_gradient_mean
        
        intermediate_mean = np.mean(output_gradient * centered_input, axis=1, keepdims=True)
        
        input_gradient = self.gamma * (centered_output_gradient - (centered_input * intermediate_mean) / input_std**2) / input_std
        
        # gradient averaging for batch processing
        gamma_gradient = np.mean(np.sum(output_gradient * normalized_input, axis=1))
        beta_gradient  = np.mean(np.sum(output_gradient, axis=1))
        
        # updating the trainable parameters (using gradient descent)
        self.gamma -= learning_rate * gamma_gradient
        self.beta  -= learning_rate * beta_gradient
        
        return input_gradient


##############################################################################


class DropoutLayer(Layer):
    """
    Dropout regularization layer
    """
    def __init__(self, dropout_rate, seed=None):
        assert (dropout_rate > 0) and (dropout_rate < 1)
        self.dropout_rate = dropout_rate
        
        self.seed = seed
        
        # all the deactivated values will be set to this value (by default)
        self.deactivated_value = 0
        
        # all the non-deactivated values will be scaled up by this factor (by default)
        self.scaling_factor = 1 / (1 - self.dropout_rate)
        
        self.nb_trainable_params = 0
    
    def __str__(self):
        precision_dropout_rate = max(2, count_nb_decimals_places(self.dropout_rate))
        return f"{self.__class__.__name__}({self.dropout_rate:.{precision_dropout_rate}f})"
    
    def generate_random_dropout_matrix(self, shape, dtype):
        """
        Returns a dropout matrix with the specified shape and datatype. For each
        row of that matrix, the values have a probability of `self.dropout_rate`
        to be deactivated (i.e. set to zero). All the non-deactivated values
        will be set to `self.scaling_factor` (i.e. 1 / (1 - self.dropout_rate))
        """
        assert len(shape) == 2
        batch_size, output_size = shape
        
        dropout_matrix = self.scaling_factor * np.ones(shape, dtype=dtype)
        nb_of_values_to_drop_per_input_sample = max(int(self.dropout_rate * output_size), 1)
        choices_for_dropped_indices = np.arange(output_size)
        
        np.random.seed(self.seed)
        for batch_sample_index in range(batch_size):
            indices_of_randomly_dropped_values = np.random.choice(choices_for_dropped_indices, size=(nb_of_values_to_drop_per_input_sample, ))
            dropout_matrix[batch_sample_index, indices_of_randomly_dropped_values] = self.deactivated_value
        np.random.seed(None) # resetting the seed
        
        return dropout_matrix
    
    def forward_propagation(self, input_data, training=True):
        """
        Returns the input with randomly deactivated values
        """
        self.input = input_data
        
        if training:
            # NB : The dropout matrix is randomly re-generated from scratch
            #      every time the forwarding method is called (during the
            #      training phase)
            self.dropout_matrix  = self.generate_random_dropout_matrix(
                shape=self.input.shape,
                dtype=self.input.dtype
            )
            self.output =  self.input * self.dropout_matrix
        else:
            # the "dropout process" does NOT apply during the validation and
            # testing phases
            self.output = self.input
        
        return self.output
    
    def backward_propagation(self, output_gradient, learning_rate):
        """
        NB : Here, `learning_rate` is not used because there are no trainable
             parameters
        """
        input_gradient = output_gradient * self.dropout_matrix
        return input_gradient

