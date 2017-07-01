import os
import os.path
import sys
import threading
import multiprocessing
import shutil
import math
import pickle
import gc
import h5py

import matplotlib
matplotlib.use('Agg')
from amuse.units import units, constants, nbody_system
from amuse.units import *

from amuse.lab import *
from amuse.units.quantities import AdaptingVectorQuantity
from amuse.datamodel import Particles, Particle
from amuse.ext import sph_to_star
from amuse.io import write_set_to_file, read_set_from_file

from amuse.plot import scatter, xlabel, ylabel, plot, pynbody_column_density_plot, HAS_PYNBODY, _smart_length_units_for_pynbody_data, convert_particles_to_pynbody_data, UnitlessArgs, semilogx, semilogy, loglog, xlabel, ylabel

from matplotlib import pyplot
import pynbody
import pynbody.plot.sph as pynbody_sph
from amuse.plot import scatter, xlabel, ylabel, plot, native_plot, sph_particles_plot

class Star:
    def __init__(self, pickleFile):
        self.pickle_file = pickleFile
        self.unpickle_stellar_structure()

    def unpickle_stellar_structure(self):
        if os.path.isfile(self.pickle_file):
            infile = open(self.pickle_file, 'rb')
        else:
            raise ("Input pickle file '{0}' does not exist".format(self.pickle_file))
        structure = pickle.load(infile)
        self.mass   = structure['mass']
        self.radius = structure['radius']
        self.number_of_zones     = structure['number_of_zones']
        self.number_of_species   = structure['number_of_species']
        self.species_names       = structure['species_names']
        self.density_profile     = structure['density_profile']
        self.radius_profile      = structure['radius_profile']
        self.mu_profile          = structure['mu_profile']
        self.composition_profile = structure['composition_profile']
        self.specific_internal_energy_profile = structure['specific_internal_energy_profile']
        self.midpoints_profile   = structure['midpoints_profile']
        self.temperature = self.specific_internal_energy_profile * self.mu_profile / (1.5 * constants.kB)
        self.sound_speed = math.sqrt((5.0/3.0) * constants.Rydberg_constant * self.temperature / self.mu_profile)

def mu(X = None, Y = 0.25, Z = 0.02, x_ion = 0.1):
    """
    Compute the mean molecular weight in kg (the average weight of particles in a gas)
    X, Y, and Z are the mass fractions of Hydrogen, of Helium, and of metals, respectively.
    x_ion is the ionisation fraction (0 < x_ion < 1), 1 means fully ionised
    """
    if X is None:
        X = 1.0 - Y - Z
    elif abs(X + Y + Z - 1.0) > 1e-6:
        print "Error in calculating mu: mass fractions do not sum to 1.0"
    return constants.proton_mass / (X*(1.0+x_ion) + Y*(1.0+2.0*x_ion)/4.0 + Z*x_ion/2.0)



def structure_from_star(star):
    radius_profile = star.radius
    density_profile = star.density_profile
    if hasattr(star, "get_mass_profile"):
        mass_profile = star.dmass * star.mass
    else:
        radii_cubed = radius_profile**3
        radii_cubed.prepend(0|units.m**3)
        mass_profile = (4.0/3.0 * constants.pi) * density_profile * (radii_cubed[1:] - radii_cubed[:-1])
        #print("Derived mass profile from density and radius.")

    return dict(
        radius = radius_profile.as_quantity_in(units.RSun),
        density = density_profile,
        mass = mass_profile,
        temperature = star.temperature,
        pressure = star.specific_internal_energy_profile,
        sound_speed = star.sound_speed
    )

def temperature_density_plot(sphGiant, step, outputDir, pickleFile):
    if not HAS_PYNBODY:
        print "problem plotting"
        return
    width = 5.0 | units.AU
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    
    sphGiant.gasParticles.temperature = 2.0/3.0 * sphGiant.gasParticles.u * mu() / constants.kB
    sphGiant.gasParticles.mu = mu()
    star = Star(pickleFile)
    data = structure_from_star(star)
    #sphGiant.gasParticles.radius = CalculateVectorSize((sphGiant.gasParticles.x,sphGiant.gasParticles.y,sphGiant.gasParticles.z))
    #data = convert_particles_to_pynbody_data(sphGiant.gasParticles, length_unit, pynbody_unit)
    figure = pyplot.figure(figsize = (8, 10))
    pyplot.subplot(1, 1, 1)
    ax = pyplot.gca()
    plotT = semilogy(data["radius"], data["temperature"], 'r-', label = r'$T(r)$')
    xlabel('Radius')
    ylabel('Temperature')
    ax.twinx()
    plotrho = semilogy(data["radius"], data["density"], 'g-', label = r'$\rho(r)$')
    plots = plotT + plotrho
    labels = [one_plot.get_label() for one_plot in plots]
    ax.legend(plots, labels, loc=3)
    ylabel('Density')

    #plot to file
    textFile = open(outputDir + '/radial_profile/temperature_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["temperature"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/density_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["density"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/radius_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["radius"]]))
    textFile.close()
    #print "saved"
    pyplot.legend()
    pyplot.suptitle('Structure of a {0} star'.format(sphGiant.mass))
    pyplot.savefig(outputDir + "/radial_profile/temperature_radial_proile_{0}".format(step))
    pyplot.close()


def Plot1Axe(x, fileName, outputDir, timeStep= 1400.0/7000.0, beginTime = 0):
    if len(x) == 0:
        return
    timeLine = [beginTime + time * timeStep for time in xrange(len(x))] | units.day
    native_plot.figure(figsize= (20, 20), dpi= 80)
    plot(timeLine,x)
    xlabel('time[days]')
    native_plot.savefig(outputDir + '/' + fileName + '.jpg')
    textFile = open(outputDir + '/' + fileName + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in x]))
    textFile.close()


def GetArgs(args):
    if len(args) > 1:
        directory=args[1]
    else:
        directory = args[0]
    if len(args) > 2:
        savingDir = directory + "/" + args[2]
        if args[2] == "snapshots":
            toCompare = False
        else:
            toCompare = True
    else:
        savingDir = directory + "/evolution"
        toCompare = True
    if len(args) > 3:
        beginStep = int(args[3])
    else:
        beginStep = 0
    if (args) > 4:
        lastStep = int(args[4])
    else:
        lastStep = 0
    if len(args) > 5:
        vmin= float(args[5])
    else:
        vmin = 1e16
    if len(args) > 6:
        vmax = float(args[6])
    else:
        vmax= 1e34
    if len(args) >7:
        opposite = True
    else:
        opposite = False
    outputDir = savingDir + "/pics"
    return savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, opposite

def InitializeSnapshots(savingDir, toCompare=False):
    '''
    taking the snapshots directory of past run
    Returns: sorted dm snapshots and gas snapshots

    '''
    snapshots = os.listdir(os.path.join(os.getcwd(),savingDir))
    numberOfSnapshots = len(snapshots) / 2
    dmFiles = []
    gasFiles = []
    for snapshotFile in snapshots:
        if 'dm' in snapshotFile: #if the word dm is in the filename
            dmFiles.append(snapshotFile)
        if 'gas' in snapshotFile:
            gasFiles.append(snapshotFile)
    if toCompare:
        dmFiles.sort(cmp=compare)
        gasFiles.sort(cmp= compare)
    else:
        dmFiles.sort()
        gasFiles.sort()
    numberOfCompanion = 0
    if len(dmFiles) > 0:
        numberOfCompanion = len(read_set_from_file(os.path.join(os.getcwd(), savingDir,dmFiles[0]), format='amuse'))
    return gasFiles, dmFiles, numberOfCompanion

def compare(st1, st2):
    num1 = int(st1.split("_")[1].split(".")[0])
    num2 = int(st2.split("_")[1].split(".")[0])
    if num1 < num2:
        return -1
    return 1


def main(args= ["../../BIGDATA/code/amuse-10.0/runs200000/run_003","evolution",0,1e16,1e34]):
    savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, opposite = GetArgs(args)
    print "plotting pics to " +  outputDir +  " from " +  savingDir +" begin step = " , beginStep , " vmin, vmax = " , vmin, vmax, "special comparing = ", toCompare
    try:
        os.makedirs(outputDir)
    except(OSError):
        pass
    try:
        os.makedirs(outputDir + "/velocity")
    except(OSError):
        pass
    try:
        os.makedirs(outputDir + "/graphs")
    except (OSError):
        pass
    try:
        os.makedirs(outputDir + "/radial_profile")
    except(OSError):
        pass
    gasFiles, dmFiles, numberOfCompanion = InitializeSnapshots(savingDir, toCompare)

    if numberOfCompanion <= 2: #binary
        print "analyzing binary"
        AnalyzeBinary(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax)
    elif numberOfCompanion ==3: #triple
        AnalyzeTriple(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, opposite)

if __name__ == "__main__":
    main(sys.argv)
