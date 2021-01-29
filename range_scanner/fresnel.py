# source: https://github.com/scottprahl/pypolar

# pylint: disable=invalid-name
"""
Useful functions for calculating light interaction at planar boundaries.

The underlying assumptions are that there a two semi-infinite media with a
planar interface.  For convenience, assume the light is incident from the top.
The upper medium is characterized by a purely real index of refraction `n_i` which
has a default value of 1.  The lower medium is characterized by a complex index
of refraction `m = n - n * kappa * 1j`.  Note that `pypolar` assumes the sign
of the imaginary part of the index of refraction is negative.

The Fresnel equations assume that the electric field has been decomposed into
fields relative to the plane of incidence (a plane defined by the incoming
light direction and the normal to the surface).

The incidence angle is measured from the normal to the surface and is measured
in radians.

To Do
    * Make sure routines work for arrays of m or of theta_i
    * fail for positive imaginary refractive indices
    * fail for out-of-range angles to catch degrees/radians error

Scott Prahl
Apr 2020
"""

import numpy as np

__all__ = ('brewster',
           'critical',
           'r_par_amplitude',
           'r_per_amplitude',
           't_par_amplitude',
           't_per_amplitude',
           'R_par',
           'R_per',
           'T_par',
           'T_per',
           'R_unpolarized',
           'T_unpolarized'
           )

def brewster(m, n_i=1):
    """
    Brewster's angle for an interface.

    Args:
        m: index of refraction of the outgoing medium [-]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        Brewster's angle from normal to surface    [radians]
    """
    return np.arctan2(m, n_i)


def critical(m, n_i=1):
    """
    Critical angle for total internal reflection at interface.

    Args:
        m: index of refraction of the outgoing medium [-]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        Critical angle from normal to surface    [radians]
    """
    return np.arcsin(m/n_i)


def r_par_amplitude(m, theta_i, n_i=1):
    """
    Reflected fraction of parallel-polarized field at an interface.

    This is the fraction of the incident electric field reflected at the
    interface between two semi-infinite media. The incident field is assumed
    to be polarized parallel (p) to the plane of incidence (transverse magnetic
    or TM field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        reflected fraction of parallel field    [-]
    """
    m2 = (m/n_i)**2
    c = m2 * np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex) # = m*cos(theta_t)
    if m.imag == 0:  # choose right branch for dielectrics
        d = np.conjugate(d)
    rp = (c - d) / (c + d)
    return np.real_if_close(rp)


def r_per_amplitude(m, theta_i, n_i=1):
    """
    Reflected fraction of perpendicular-polarized field at an interface.

    This is the fraction of the incident electric field reflected at the
    interface between two semi-infinite media. The incident field is assumed
    to be polarized perpendicular (s, or senkrecht) to the plane of incidence
    (transverse electric or TE field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        reflected fraction of perpendicular field [-]
    """
    m2 = (m/n_i)**2
    c = np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex) # = m*cos(theta_t)
    if m.imag == 0:  # choose right branch for dielectrics
        d = np.conjugate(d)
    rs = (c - d) / (c + d)
    return np.real_if_close(rs)


def t_par_amplitude(m, theta_i, n_i=1):
    """
    Transmitted fraction of parallel-polarized field through an interface.

    This is the fraction of the incident electric field transmitted through the
    interface between two semi-infinite media. The incident field is assumed
    to be polarized parallel (p) to the plane of incidence (transverse magnetic
    or TM field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        transmitted fraction of parallel field                [-]
    """
    m2 = (m/n_i)**2
    c = np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex) # = m*cos(theta_t)
    if m.imag == 0:  # choose right branch for dielectrics
        d = np.conjugate(d)
    tp = 2 * c * (m/n_i) / (m2 * c + d)
    return np.real_if_close(tp)


def t_per_amplitude(m, theta_i, n_i=1):
    """
    Transmitted fraction of perpendicular-polarized field through an interface.

    This is the fraction of the incident electric field transmitted through the
    interface between two semi-infinite media. The incident field is assumed
    to be polarized perpendicular (s, or senkrecht) to the plane of incidence
    (transverse electric or TE field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        transmitted fraction of perpendicular field [-]
    """
    m2 = (m/n_i)**2
    c = np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex) # = m*cos(theta_t)
    if m.imag == 0:  # choose right branch for dielectrics
        d = np.conjugate(d)
    ts = 2 * d / (m/n_i)/ (c + d)
    return np.real_if_close(ts)


def R_par(m, theta_i, n_i=1):
    """
    Reflected fraction of parallel-polarized optical power by an interface.

    The reflected fraction of incident power (or flux) assuming that
    the electric field of the incident light is polarized parallel (p) to the
    plane of incidence (transverse magnetic or TM electric field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        reflected fraction of parallel-polarized irradiance [-]
    """
    return abs(r_par_amplitude(m, theta_i, n_i))**2


def R_per(m, theta_i, n_i=1):
    """
    Reflected fraction of perpendicular-polarized optical power by an interface.

    The fraction of the incident power (or flux) reflected at the
    interface between two semi-infinite media. The incident light is assumed
    to be polarized perpendicular (s, or senkrecht) to the plane of incidence
    (transverse electric or TE field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        reflected fraction of perpendicular-polarized irradiance [-]
    """
    return abs(r_per_amplitude(m, theta_i, n_i))**2


def T_par(m, theta_i, n_i=1):
    """
    Transmitted fraction of parallel-polarized optical power through an interface.

    The transmitted fraction of incident power (or flux) assuming that
    the electric field of the incident light is polarized parallel (p) to the
    plane of incidence (transverse magnetic or TM electric field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        transmitted fraction of parallel-polarized irradiance [-]
    """
    m2 = (m/n_i)**2
    c = np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex)
    tp = 2 * c * (m/n_i) / (m2 * c + d)
    return np.abs(d / c * abs(tp)**2)


def T_per(m, theta_i, n_i=1):
    """
    Transmitted fraction of perpendicular-polarized optical power through an interface.

    The transmitted fraction of the incident power (or flux) through the
    interface between two semi-infinite media. The incident light is assumed
    to be polarized perpendicular (s, or senkrecht) to the plane of incidence
    (transverse electric or TE field).

    The index of refraction for medium of the incoming field defaults to 1, but
    can be set any real value. The medium of the outgoing field is characterized
    by an index of refraction that may be complex.

    Args:
        m: complex index of refraction of the outgoing medium [-]
        theta_i: angle incident from normal to surface        [radians]
        n: real index of refraction of the incoming medium    [-]
    Returns:
        transmitted fraction of perpendicular-polarized irradiance [-]
    """
    m2 = (m/n_i)**2
    c = np.cos(theta_i)
    s = np.sin(theta_i)
    d = np.sqrt(m2 - s * s, dtype=np.complex)
    ts = 2 * c / (c + d)
    return np.abs(d / c * abs(ts)**2)


def R_unpolarized(m, theta_i, n_i=1):
    """
    Fraction of unpolarized light that is reflected.

    Calculate reflection fraction of incident power (or flux) assuming that
    the incident light is unpolarized

    Args:
        m :     complex index of refraction   [-]
        theta_i : incidence angle from normal [radians]
    Returns:
        reflected irradiance                  [-]
    """
    return (R_par(m, theta_i, n_i) + R_per(m, theta_i, n_i)) / 2


def T_unpolarized(m, theta_i, n_i=1):
    """
    Fraction of unpolarized light that is transmitted.

    Calculate transmitted fraction of incident power (or flux) assuming that
    the incident light is unpolarized

    Args:
        m :     complex index of refraction   [-]
        theta_i : incidence angle from normal [radians]
    Returns:
        reflected irradiance                  [-]
    """
    return (T_par(m, theta_i, n_i) + T_per(m, theta_i, n_i)) / 2