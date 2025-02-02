# -*- coding: utf-8 -*-
##################################################
# © 2017 ETH Zurich, Swiss Seismological Service #
# Stefano Marano' - wavedec at gmail dot com     #
##################################################
"""
Here are some functions for circular statistics
"""

import numpy as np
import itertools, math
import warnings
import matplotlib.pyplot as plt
from scipy import linalg

from numpy import atleast_2d, reshape, zeros, newaxis, dot, exp, pi, sqrt, \
    power, sum


def circ_mean(alpha, axis=None):
    
    
    mu = np.arctan2(np.mean(np.sin(alpha),axis),np.mean(np.cos(alpha),axis))
    mu = np.mod(mu, 2 * np.pi)
    return mu


def circ_r(alpha, axis=None):
    """
    input
        alpha: angles
    returns
        r: mean resultant length
    """
    if axis is None:
         N = np.size(alpha)
    else:
         N = np.shape(alpha, axis)
         
    r = np.sqrt(np.sum(np.sin(alpha),axis)**2 + np.sum(np.cos(alpha),axis)**2)/N
    
    return r
    
def circ_var(alpha, axis=None):
    """
    input
        alpha: angles
    returns
        r: circular variance
    """
        
    r = circ_r(alpha,axis)
    v = 1-r
    return v
    
def circ_std(alpha, axis=None):
    """
    input
        alpha: angles
    returns
        s: circular standard
    """

    r = circ_r(alpha,axis)
    s = np.sqrt(-2*np.log(r))
    
    return s

def cdiff(alpha, beta):
    """
    Difference between pairs :math:`x_i-y_i` around the circle,
    computed efficiently.
    :param alpha:  sample of circular random variable
    :param beta:   sample of circular random variable
    :return: distance between the pairs
    """
    return np.angle(np.exp(1j * alpha) / np.exp(1j * beta))

def pairwise_cdiff(alpha, beta=None):
    """
    All pairwise differences :math:`x_i-y_j` around the circle,
    computed efficiently.
    :param alpha: sample of circular random variable
    :param beta: sample of circular random variable
    :return: array with pairwise differences
    References: [Zar2009]_, p. 651
    """
    if beta is None:
        beta = alpha

    # advanced slicing and broadcasting to make pairwise distance work
    # between arbitrary nd arrays
    reshaper_alpha = len(alpha.shape) * (slice(None, None),) + \
        len(beta.shape) * (np.newaxis,)
    reshaper_beta = len(alpha.shape) * (np.newaxis,) + \
        len(beta.shape) * (slice(None, None),)

    return np.angle(np.exp(1j * alpha[reshaper_alpha]) /
                    np.exp(1j * beta[reshaper_beta]))
                    
                    
def circ_median(alpha, axis=None, bootstrap_iter=None):
    """
    Computes the median direction for circular data.
    :param alpha: sample of angles in radians
    :param axis:  compute along this dimension,
                  default is None (across all dimensions)
    :param ci:    if not None, the upper and lower 100*ci% confidence
                  interval is returned as well
    :param bootstrap_iter: number of bootstrap iterations
                           (number of samples if None)
    :return: median direction
    """
    if axis is None:
        axis = 0
        alpha = alpha.ravel()

    dims = [range(alpha.shape[i]) for i in range(len(alpha.shape))]
    dims[axis] = [slice(None)]

    med = np.empty(alpha.shape[:axis] + alpha.shape[axis + 1:])
    n = alpha.shape[axis]
    is_odd = (n % 2 == 1)
    for idx in itertools.product(*dims):
        out_idx = idx[:axis] + idx[axis + 1:]

        beta = np.mod(alpha[idx], 2 * np.pi)

        dd = pairwise_cdiff(beta)

        m1 = np.sum(dd >= 0, 0)
        m2 = np.sum(dd <= 0, 0)
        dm = np.abs(m1 - m2)

        #if is_odd:
        #    min_idx = np.argmin(dm)
        #    m = dm[min_idx]
        #else:
        #    m = np.min(dm)
        #    # min_idx = np.argsort(dm)[:2] # this is the original but may be not good
        #    min_idx = np.where(dm == m)[0]
        m = np.min(dm)
        min_idx = np.where(dm == m)[0]
        if m > 1:
            warnings.warn('Ties detected in median computation')

        md = circ_mean(beta[min_idx])

        if np.abs(cdiff(circ_mean(beta), md)) > np.abs(cdiff(circ_mean(beta), md + np.pi)):
            md = np.mod(md + np.pi, 2 * np.pi)

        med[out_idx] = md
        
        med = np.mod(med, 2 * np.pi)

    return med

class CircKde(object):
    """
    This class provides basic functionalities to estimate a density for angular data.
    The code is an adapted and simplified version of scipy/stats/kde.py

    """
    def __init__(self, dataset, bw_method=None, modularity=None):
        self.dataset = atleast_2d(dataset)
        if not self.dataset.size > 1:
            raise ValueError("`dataset` input should have multiple elements.")

        self.d, self.n = self.dataset.shape
        self.set_bandwidth(bw_method=bw_method, modularity=modularity)

    def evaluate(self, points):
        """Evaluate the estimated pdf on a set of points.

        Parameters
        ----------
        points : (# of dimensions, # of points)-array
            Alternatively, a (# of dimensions,) vector can be passed in and
            treated as a single point.

        Returns
        -------
        values : (# of points,)-array
            The values at each point.

        Raises
        ------
        ValueError : if the dimensionality of the input points is different than
                     the dimensionality of the KDE.

        """
        
        # TODO this funtcion should also be adapted for modular stuff
        points = atleast_2d(points)

        d, m = points.shape
        if d != self.d:
            if d == 1 and m == self.d:
                # points was passed in as a row vector
                points = reshape(points, (self.d, 1))
                m = 1
            else:
                msg = "points have dimension %s, dataset has dimension %s" % (d,
                    self.d)
                raise ValueError(msg)

        result = zeros((m,), dtype=np.float)

        if not math.isnan(self.inv_cov):
            if not self.modular:
                if m >= self.n:
                    # there are more points than data, so loop over data
                    for i in range(self.n):
                        diff = self.dataset[:, i, newaxis] - points
                        tdiff = dot(self.inv_cov, diff)
                        energy = sum(diff*tdiff,axis=0) / 2.0
                        result = result + exp(-energy)
                else:
                    # loop over points
                    for i in range(m):
                        diff = self.dataset - points[:, i, newaxis]
                        tdiff = dot(self.inv_cov, diff)
                        energy = sum(diff * tdiff, axis=0) / 2.0
                        result[i] = sum(exp(-energy), axis=0)
            else:
                if m >= self.n:
                    # there are more points than data, so loop over data
                    for i in range(self.n):
                        diff = cdiff(self.modularity_factor*self.dataset[:, i, newaxis], self.modularity_factor*points)/self.modularity_factor
                        tdiff = dot(self.inv_cov, diff)
                        energy = sum(diff*tdiff,axis=0) / 2.0
                        result = result + exp(-energy)
                else:
                    # loop over points
                    for i in range(m):
                        diff = cdiff(self.modularity_factor*self.dataset, self.modularity_factor*points[:, i, newaxis])/self.modularity_factor
                        tdiff = dot(self.inv_cov, diff)
                        energy = sum(diff * tdiff, axis=0) / 2.0
                        result[i] = sum(exp(-energy), axis=0)
            
            result = result / self._norm_factor

        return result

    __call__ = evaluate



    def scotts_factor(self):
        return power(self.n, -1./(self.d+4))

    def silverman_factor(self):
        return power(self.n*(self.d+2.0)/4.0, -1./(self.d+4))

    #  Default method to calculate bandwidth, can be overwritten by subclass
    covariance_factor = scotts_factor
    covariance_factor.__doc__ = """Computes the coefficient (`kde.factor`) that
        multiplies the data covariance matrix to obtain the kernel covariance
        matrix. The default is `scotts_factor`.  A subclass can overwrite this
        method to provide a different method, or set it through a call to
        `kde.set_bandwidth`."""

    def set_bandwidth(self, bw_method=None, modularity=None):
        """Compute the estimator bandwidth with given method.

        The new bandwidth calculated after a call to `set_bandwidth` is used
        for subsequent evaluations of the estimated density.

        Parameters
        ----------
        bw_method : str, scalar or callable, optional
            The method used to calculate the estimator bandwidth.  This can be
            'scott', 'silverman', a scalar constant or a callable.  If a
            scalar, this will be used directly as `kde.factor`.  If a callable,
            it should take a `gaussian_kde` instance as only parameter and
            return a scalar.  If None (default), nothing happens; the current
            `kde.covariance_factor` method is kept.
        modularity: specifies whether the values refer to an angle and circular variance should be used instead of variance

      

        """
        if np.isscalar(bw_method):
            self.covariance_factor = lambda: bw_method
        else:
            msg = "`bw_method` should be a scalar"
            raise ValueError(msg)
            
        if modularity is None:
            self.modular = False
        elif np.isscalar(modularity):
            self.modular = True
            self.modularity_factor = 2*np.pi/modularity
        else:
            msg = "`modularity` should be None or a scalar or a callable."
            raise ValueError(msg)

        self._compute_covariance()

    def _compute_covariance(self):
        """Computes the covariance matrix for each Gaussian kernel using
        covariance_factor().
        """
        self.factor = self.covariance_factor()
        # Cache covariance and inverse covariance of the data
        if not hasattr(self, '_data_inv_cov'):
            if not self.modular:
                self._data_covariance = atleast_2d(np.cov(self.dataset, rowvar=1,
                                                          bias=False))
            else:
                self._data_covariance = atleast_2d( \
                (circ_std(self.modularity_factor*self.dataset)/self.modularity_factor)**2 )
                
            self._data_inv_cov = 1/self._data_covariance if self._data_covariance > 0 else np.nan
                

        self.covariance = self._data_covariance * self.factor**2
        self.inv_cov = self._data_inv_cov / self.factor**2
        self._norm_factor = sqrt(linalg.det(2*pi*self.covariance)) * self.n
    
if __name__ == "__main__":
    plt.close('all')
    N = 1001
    std = 0.5
    mu = 6.2
    x = std*np.random.randn(N) + mu
    x = np.mod(x, 2*np.pi)
    x_vec = np.linspace(0, 2*np.pi, 200)
    print("\nfirst test")
    print(np.mean(x))
    print(circ_mean(x))
    print(circ_median(x))
    print(circ_std(x))
    print(circ_var(2*x)/2)
    

    
    
    plt.figure()
    n, bins, patches = plt.hist(x, 50, normed=1, facecolor='green', alpha=0.75)
    plt.plot([mu, mu], [0, np.max(n)*1.1], 'k', linewidth=2)
    plt.plot(circ_mean(x), 0, 'r+', markersize=15, markeredgewidth=3)
    plt.plot(circ_median(x), 0, 'bx', markersize=15, markeredgewidth=3)
    plt.xlim([0 , 2*np.pi])
    
    
    
    
    kernel = CircKde(x, bw_method=0.2)
    density = kernel(x_vec)
    
    kernel2 = CircKde(x, bw_method=0.2, modularity=2*np.pi)
    density2 = kernel2(x_vec)
    
    plt.figure()
    plt.plot(x_vec, density, 'b')
    plt.plot(x_vec, density2, 'r')
    plt.xlim([0 , 2*np.pi])
    plt.show()
    
    
    if True:
        mu = 3
        x = std*np.random.randn(N) + mu
        x = np.mod( x, np.pi)
        x_vec = np.linspace(0, np.pi, 200)

        print("\nsecond test")        
        print(np.mean(x))
        print(circ_mean(2*x)/2 )
        print(circ_median(2*x)/2 )
        print(circ_std(2*x)/2)
        print(circ_var(2*x)/2)
        
        #print( circ_std( 2*(x+np.pi/2) )/2 -np.pi/2 )
        
        plt.figure()
        n, bins, patches = plt.hist(x, 50, normed=1, facecolor='green', alpha=0.75)
        plt.plot([mu, mu], [0, np.max(n)*1.1], 'k', linewidth=2)
        plt.plot(circ_mean( 2*x )/2, 0, 'r+', markersize=15, markeredgewidth=3)
        plt.plot(circ_median( 2*x )/2, 0, 'bx', markersize=15, markeredgewidth=3)
        plt.xlim([0 , np.pi])
        
           
        kernel = CircKde(x, bw_method=0.2)
        density = kernel(x_vec)
        
        kernel2 = CircKde(x, bw_method=0.2, modularity=np.pi)
        density2 = kernel2(x_vec)
        
        plt.figure()
        plt.plot(x_vec, density, 'b')
        plt.plot(x_vec, density2, 'r')
        plt.xlim([0 , np.pi])
        plt.show()
