# %% preamble
import os
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
WORKSPACE_ROOT = REPO_ROOT.parent
MATPOWER_ROOT = WORKSPACE_ROOT / "matpower"
DCOPF_DIR = REPO_ROOT / "DC-opf model"

if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

print("python path added:", THIS_DIR)

import numpy as np
import math
import scipy.io
from scipy.stats import norm
import multiprocessing as mp
import matlab
import matlab.engine
import pickle

from rips import *
from rips.feyman_kac import StandardGaussian
from rips.utils import FeynmanKac, Particle

# %% settings for the problem

caseName        = 'case14'
blackoutSizeThr = 54.8
pf              = 1.1373*10**-4

method          = 'iPIM_aPIM'
s_factor        = 10
N               = 100
nRun            = 1
batchSize       = 1

# %% define the DC optimal power flow class
class dcopt(FeynmanKac, StandardGaussian):
    def __init__(self, thr: float, mpc: dict, eng, **kwargs):
        self.eng   = eng
        self.thr   = thr
        self.alpha = 2.0
        self.mpc   = eng.add_branchCapacity(mpc, self.alpha)

        self.set_probablisticModel(**kwargs)
        self.get_networkInfo()

        super().__init__(**kwargs)

    def set_probablisticModel(self, **kwargs):
        if 'distrGen' in kwargs:
            self.distrGen = kwargs['distrGen']
        else:
            self.distrGen = [[1, 0.6, 0.2, 0], [0.01, 0.2, 0.5, 1]]
        if 'distrOrdinaryBus' in kwargs:
            self.distrOrdinaryBus = kwargs['distrOrdinaryBus']
        else:
            self.distrOrdinaryBus = [[1, 0], [0.01, 1]]
        if 'distrBranch' in kwargs:
            self.distrBranch = kwargs['distrBranch']
        else:
            self.distrBranch = [[1, 0], [0.01, 1]]

    def get_networkInfo(self):
        self.nb  = len(self.mpc['bus'])
        self.ng  = len(self.mpc['gen'])
        self.nl  = len(self.mpc['branch'])
        self.busDic    = [int(self.mpc['bus'][i][0]) for i in range(self.nb)]
        self.genDic    = [int(self.mpc['gen'][i][0]) for i in range(self.ng)]
        self.branchDic = [[int(self.mpc['branch'][i][0]), int(self.mpc['branch'][i][1])] for i in range(self.nl)]

    def response(self, path: np.ndarray, level: int) -> np.ndarray:
        systemState = []
        for d in range(self.nb):
            if self.busDic[d] in self.genDic:
                idx = np.argwhere(norm.cdf(path[d]) <= self.distrGen[1])
                systemState.append([self.distrGen[0][int(idx[0][0])]])
            else:
                idx = np.argwhere(norm.cdf(path[d]) <= self.distrOrdinaryBus[1])
                systemState.append([self.distrOrdinaryBus[0][int(idx[0][0])]])

        for d in range(self.nb, self.nb + self.nl):
            idx = np.argwhere(norm.cdf(path[d]) <= self.distrBranch[1])
            systemState.append([self.distrBranch[0][int(idx[0][0])]])

        blackoutSize = self.eng.func_dcopt(matlab.double(systemState), self.mpc)
        return blackoutSize

    def score_function(self, particle: Particle) -> float:
        return particle.response / self.thr

    @property
    def num_variables(self) -> int:
        return self.nb + self.nl

# %% function for parallel
def iPIM_aPIM(iRun):
    eng = matlab.engine.start_matlab()

    eng.addpath(eng.genpath(str(MATPOWER_ROOT)), nargout=0)
    eng.addpath(str(DCOPF_DIR), nargout=0)
    eng.eval("rehash", nargout=0)

    print("matlab paths added")
    print("loadcase ->", eng.which("loadcase"))
    print("add_branchCapacity ->", eng.which("add_branchCapacity"))
    print("func_dcopt ->", eng.which("func_dcopt"))

    mpc0 = eng.loadcase(caseName)
    if 'bus_name' in mpc0.keys():
        del mpc0['bus_name']
    print("case loaded")

    model = dcopt(thr=blackoutSizeThr, mpc=mpc0, eng=eng)
    model.num_of_particles = N
    model.s_factor         = s_factor
    print("model created")

    kernels = [PCN()]
    results = ComboUQ(model, kernels)

    eng.quit()
    print("finished run", iRun)

    return results.summary_results()

# %% smoke test run
if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    fileName = f"batch0_{caseName}_thr{blackoutSizeThr}_iPIM+aPIM_N{N}"

    with mp.Pool(1) as my_pool:
        results = my_pool.map(iPIM_aPIM, [0])

    estpf_officialRun   = [results[i]['p_bar'] for i in range(len(results))]
    estpf_pilotRun      = [results[i]['p_smc'] for i in range(len(results))]
    numOfParticles_aPIM = [results[i]['ng_gs'] for i in range(len(results))]
    numOfParticles_iPIM = [results[i]['ng_smc'] for i in range(len(results))]

    with open(fileName, 'wb') as file:
        pickle.dump([estpf_officialRun, estpf_pilotRun, numOfParticles_aPIM, numOfParticles_iPIM], file)

    print("wrote:", fileName)
