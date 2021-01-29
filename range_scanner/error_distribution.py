import numpy as np

# for more distributions see: https://numpy.org/doc/stable/reference/random/generator.html#distributions

def applyNoise(mu, sigma):
    return np.random.default_rng().normal(mu, sigma, None)