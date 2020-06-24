import numpy as np
from numpy import linalg as la


def get_Ham(n, x, y, z, spin):
    cap_n = np.power(2, n)
    Ham = np.zeros(cap_n, cap_n)
    c1 = z
    for i in range(1, n):
        e1=np.eye(np.power(2,(i-1)))
        e2=np.eye(np.power(2,(n-i)))
        c = np.kron(np.kron(e1,c1),e2)
        Ham=Ham+c*spin[i-1,i-1]

        for j in range(i+1, n+1):  # changed n+1 -> n
            J_Coupling = spin[i-1,j-1]
            e1 = np.eye(np.power(2, (i-1)))
            e2 = np.eye(np.power(2, (j-i-1)))
            e3 = np.eye(np.power(2, (n-j)))
            cout1=np.kron(np.kron(np.kron(np.kron(e1,x),e2),x),e3)
            cout2=np.kron(np.kron(np.kron(np.kron(e1,y),e2),y),e3)
            cout3=np.kron(np.kron(np.kron(np.kron(e1,z),e2),z),e3)
            Ham = Ham+(cout1+cout2+cout3)*J_Coupling

    i = n
    c1 = z
    e1 = np.eye(np.power(2,(i-1)))
    e2 = np.eye(np.power(2,(n-i)))
    c = np.kron(np.kron(e1,c1),e2)
    Ham = Ham+c*spin[i-1, i-1]

    return Ham


def get_OBS(n, State,y):
    OBS = State
    c1 = y
    for _ in range(n):
        i = _+1
        e1 = np.eye(np.power(2,(i-1)))
        e2 = np.eye(np.power(2, (n-i)))
        c = np.kron(np.kron(e1, c1), e2)
        OBS = OBS+1j*c
    return OBS


def get_State(n, x):  # compared; OK!
    cap_n = np.power(2, n)
    State = np.zeros(cap_n)
    c1=x
    for _ in range(n):
        i = _+1
        e1 = np.eye(np.power(2,(i-1)))
        e2 = np.eye(np.power(2, (n-i)))
        c = np.kron(np.kron(e1, c1), e2)
        State = State+c
    return State


def do_dot(a, b):
    inner = []
    for _ in range(len(a)):
        inner.append(a[_] * b[_])
    d = np.asarray(inner)
    return d


def mean_zeros(fid):
    hist, bin_edges = np.histogram(fid, density=True)
    index = np.argmax(hist)
    fid -= bin_edges[index]
    return fid


def calculate_spectrum(input_parameters):
    e = np.eye(2)
    x = 0.5*np.fliplr(e)
    z = 0.5*e
    z[1, 1] = -0.5
    y = 1j * (np.matmul(z, x) - np.matmul(x, z))
    spin_matrix = input_parameters["spin_matrix"]
    spin_len = len(spin_matrix)
    State = get_State(spin_len, x)
    OBS = get_OBS(spin_len, State, y)
    Ham=get_Ham(spin_len,x, y, z, spin_matrix)
    Ham = Ham.real
    [s, v] = la.eig(np.array(Ham))  # vector, matrix
    v = v.real
    s = s.real

    idx = s.argsort()
    s = s[idx]
    v = v[:, idx]

    mask_thresh = 0.001
    v = do_dot(v, abs(v) >= mask_thresh * v.max())
    ar = do_dot(np.matmul(v.transpose(), np.matmul(OBS, v)), np.matmul(v.transpose(), np.matmul(State, v)))
    ar = do_dot(ar, abs(ar) >= mask_thresh*ar.max())
    ar = ar.real
    xx = []
    yy = []
    c = []
    for _ in range(ar.shape[0]):
        for __ in range(ar.shape[1]):
            if ar[_][__] != 0:
                xx.append(_)
                yy.append(__)
                c.append(ar[_][__])

    c = np.asarray(c)
    c = c/c.max()
    trans_x = abs(s[xx]-s[yy])/input_parameters["field"]
    trans_y = c
    ppm = np.asarray([x*13/input_parameters["numpoints"]-1 for x in range(input_parameters["numpoints"])])

    spectrum = np.zeros(ppm.shape)
    for _ in range(len(trans_x)):
        c_ppm = trans_x[_]
        index = np.argmin(abs(ppm-c_ppm))
        spectrum[index] += trans_y[_]
    fd = np.fft.ifft(spectrum)
    dw = input_parameters["dw"]
    lw = input_parameters["line_width"]
    lor_coeff = input_parameters["lor_coeff"]
    gau_coeff = input_parameters["gau_coeff"]
    t = np.asarray(range(len(fd)))
    ex = np.asarray(lor_coeff*np.exp(-t*dw*np.pi*lw)+gau_coeff*np.exp(-t*dw*np.pi*lw))
    d = do_dot(ex, fd)

    sim_fid = (np.fft.fft(d))
    sim_fid = sim_fid.real
    sim_fid = np.asarray(sim_fid)
    sim_fid = sim_fid/sim_fid.max()
    sim_fid = mean_zeros(sim_fid)
    return ppm, sim_fid
