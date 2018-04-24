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
import argparse
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
from amuse.plot import scatter, xlabel, ylabel, plot, native_plot, sph_particles_plot, circle_with_radius, axvline
from BinaryCalculations import *

class Star:
    def __init__(self, particle1,particle2):
        if particle1 != None and particle2 != None:
            self.Star(particle1,particle2)
        else:
            self.position = (0.0, 0.0, 0.0) | units.m
            self.vx, self.vy, self.vz = (0.0 , 0.0, 0.0 ) | units.m / units.s
            self.v = 0.0 | units.m / units.s
            self.mass = 0.0 | units.kg

    def Star(self,particle1,particle2):
        self.vx = (particle1.vx* particle1.mass + particle2.vx * particle2.mass)/(particle1.mass + particle2.mass)
        self.vy = (particle1.vy* particle1.mass + particle2.vy * particle2.mass)/(particle1.mass + particle2.mass)
        self.vz = (particle1.vz* particle1.mass + particle2.vz * particle2.mass)/(particle1.mass + particle2.mass)
        self.v = CalculateVectorSize((self.vx,self.vy,self.vz))
        self.x = (particle1.x* particle1.mass + particle2.x * particle2.mass)/(particle1.mass + particle2.mass)
        self.y = (particle1.y * particle1.mass + particle2.y * particle2.mass)/(particle1.mass + particle2.mass)
        self.z = (particle1.z * particle1.mass + particle2.z * particle2.mass)/(particle1.mass + particle2.mass)
        self.position =(self.x, self.y, self.z)
        self.mass  = particle1.mass + particle2.mass
        self.velocityDifference = CalculateVelocityDifference(particle1,particle2)
        self.separation = CalculateSeparation(particle1,particle2)
        self.specificEnergy = CalculateSpecificEnergy(self.velocityDifference,self.separation,particle1,particle2)

class SphGiant:
    def __init__(self, gas_particles_file, dm_particles_file, opposite= False):
        self.gasParticles = read_set_from_file(gas_particles_file, format='amuse')
        if dm_particles_file is not None:
            dms = read_set_from_file(dm_particles_file, format='amuse')
            if opposite: #core is the first particle
                self.core = dms[0]
            else:
                self.core = dms[-1]
        else:
            self.core = Particle()
            self.core.mass = 0 | units.MSun
            self.core.position = (0.0, 0.0, 0.0) | units.AU
            self.core.vx = 0.0| units.m/units.s
            self.core.vy = 0.0 | units.m/units.s
            self.core.vz = 0.0 | units.m/units.s
            self.core.radius = 0.0 | units.RSun
        self.gas = Star(None, None)
        self.gas.mass = self.gasParticles.total_mass()
        self.gas.position = self.gasParticles.center_of_mass()
        self.gas.x , self.gas.y, self.gas.z = self.gasParticles.center_of_mass()
        self.gas.vx, self.gas.vy, self.gas.vz = self.gasParticles.center_of_mass_velocity()
        self.gas.v = (self.gas.vx, self.gas.vy, self.gas.vz)
        #print "gas position: ", self.gas.position, " core position: ", self.core.position
        self.mass = self.gas.mass + self.core.mass
        #print "core mass: ",self.core.mass.as_quantity_in(units.MSun)," gas mass: ", self.gas.mass.as_quantity_in(units.MSun), " total star mass: ", self.mass.as_quantity_in(units.MSun)
        self.x , self.y, self.z = (self.gas.position * self.gas.mass + self.core.position * self.core.mass) / self.mass
        #self.x , self.y, self.z = self.core.position
        self.vx, self.vy, self.vz = (self.gas.v * self.gas.mass + (self.core.vx, self.core.vy, self.core.vz) * self.core.mass) / self.mass
        #self.vx, self.vy, self.vz =  self.core.vx, self.core.vy, self.core.vz
        self.v = (self.vx, self.vy, self.vz)
        self.position = (self.x,self.y,self.z)
        self.radius = self.gasParticles.total_radius()

    def CalculateInnerSPH(self, relativeParticle):
        self.innerGas = Star(None, None)
        radius = CalculateVectorSize(CalculateSeparation(relativeParticle, self.core))
        self.CalculateSphMassVelocityAndPositionInsideRadius(radius)
        self.innerGas.x , self.innerGas.y, self.innerGas.z = self.innerGas.position
        print "calculated!"
    def CalculateTotalGasMassInsideRadius(self, radius):
        innerMass = self.core.mass
        i = 0
        for particle in self.gasParticles:
            separation = CalculateVectorSize(CalculateSeparation(particle, self.core))
            if separation < radius:
                innerMass += particle.mass
        return innerMass

    def CalculateSphMassVelocityAndPositionInsideRadius(self,radius):
        self.innerGas.mass = self.core.mass
        self.innerGas.vxTot , self.innerGas.vyTot , self.innerGas.vzTot = ( 0.0 , 0.0, 0.0 )| units.m * units.s**-1
        self.innerGas.xTot , self.innerGas.yTot , self.innerGas.zTot = ( 0.0 , 0.0, 0.0 )| units.m
        cmass = self.core.mass.value_in(units.MSun)
        velocityAndMass = (self.core.vx * cmass, self.core.vy * cmass,self.core.vz * cmass)
        positionAndMass = (self.core.x * cmass, self.core.y * cmass,self.core.z * cmass)

        particles = 0
        for particle in self.gasParticles:
            separation = CalculateVectorSize(CalculateSeparation(particle, self.core))
            if separation < radius:
                pmass = particle.mass.value_in(units.MSun)
                self.innerGas.mass += particle.mass
                velocityAndMass += (particle.vx * pmass, particle.vy * pmass, particle.vz * pmass)
                positionAndMass += (particle.x * pmass, particle.y * pmass, particle.z * pmass)
                particles += 1
        print particles
        if particles > 0:
            totalMass=  self.innerGas.mass.value_in(units.MSun)
            self.innerGas.vxTot = velocityAndMass[0] / totalMass
            self.innerGas.vyTot = velocityAndMass[1] / totalMass
            self.innerGas.vzTot = velocityAndMass[2] / totalMass

            self.innerGas.xTot = positionAndMass[0] / totalMass
            self.innerGas.yTot = positionAndMass[1] / totalMass
            self.innerGas.zTot = positionAndMass[2] / totalMass
        self.innerGas.v = (self.innerGas.vxTot, self.innerGas.vyTot, self.innerGas.vzTot)
        self.innerGas.position = (self.innerGas.xTot, self.innerGas.yTot, self.innerGas.zTot)

    def CountLeavingParticlesInsideRadius(self):
        leavingParticles = 0
        for particle in self.gasParticles:
            specificEnergy = CalculateSpecificEnergy(CalculateVelocityDifference(particle,self.gas),CalculateSeparation(particle, self.gas), particle, self.gas)
            if specificEnergy > 0:
                leavingParticles += 1
        return leavingParticles

def LoadBinaries(file, opposite= False):
    load = read_set_from_file(file, format='amuse')
    #print load
    if not opposite:
        stars = Particles(2, particles= [load[0], load[1]])
    else: #take the next
        stars = Particles(2, particles= [load[1], load[2]])
    return stars


def GetPropertyAtRadius(mesaStarPropertyProfile, mesaStarRadiusProfile, radius):
    profileLength = len(mesaStarRadiusProfile)
    i = 0
    while i < profileLength and mesaStarRadiusProfile[i] < radius:
        i += 1
    return mesaStarPropertyProfile[min(i, profileLength - 1)]


def CalculateCumulantiveMass(densityProfile, radiusProfile):
    profileLength = len(radiusProfile)
    cmass = [densityProfile[0] * 4.0/3.0 * constants.pi * radiusProfile[0] ** 3 for i in xrange(profileLength)]
    for i in xrange(1, profileLength):
        dr = radiusProfile[i] - radiusProfile[i-1]
        cmass[i] = (cmass[i-1] + densityProfile[i] * 4.0 * constants.pi*(radiusProfile[i] ** 2) * dr)
    vectormass = [m.value_in(units.MSun) for m in cmass]
    return vectormass

def CalculateTau(densityProfile, radiusProfile, coreRadius, coreDensity,temperatureProfile, edgeRadius):
    profileLength = len(radiusProfile)
    radiusIndex = 0
    while radiusProfile[radiusIndex] < edgeRadius:
            radiusIndex += 1

    X= 0.73
    Y = 0.25
    Z= 0.02
    #kappa = 0.2 * (1 + X) | (units.cm**2)*(units.g**-1)
    kappa = 12.0 | units.cm**2 / units.g
    #kappa = (3.8*10**22)*(1 + X)* (X + Y)* densityProfile * temperatureProfile**(-7.0/2)
    #print kappa
    tauPoint = [kappa * densityProfile[i] * (radiusProfile[i+1] - radiusProfile[i]) for i in xrange(0, radiusIndex)]
    tauPoint.append((0.0 |(units.g*units.cm**-2))*kappa)
    tau = tauPoint
    tau[radiusIndex] = tauPoint[radiusIndex]
    for i in xrange(radiusIndex - 1, 0 , -1 ):
        tau[i] = tau[i + 1] + tauPoint[i]
    print tau[-1], tau[-100]
    i = radiusIndex
    while (tau[i] < 2.0/3.0 and i >= 0):
        i -= 1
    j = radiusIndex
    while (tau[j] < 13.0 and j >= 0):
        j -= 1

    #print "edge: ", radiusProfile[radiusIndex].as_quantity_in(units.RSun), " at index= ",radiusIndex, " photosphere radius: ", \
    #    radiusProfile[i].as_quantity_in(units.RSun), " at index= ", i, "tau is 13 at radius= ", radiusProfile[j].as_quantity_in(units.RSun)
    return tau

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
    density_profile = star.rho
    if hasattr(star, "get_mass_profile"):
        mass_profile = star.dmass * star.mass
    else:
        radii_cubed = radius_profile**3
        radii_cubed.prepend(0|units.m**3)
        mass_profile = (4.0/3.0 * constants.pi) * density_profile * (radii_cubed[1:] - radii_cubed[:-1])
    cumulative_mass_profile = CalculateCumulantiveMass(density_profile, radius_profile)
    tau = CalculateTau(density_profile, radius_profile, 0.0159 | units.RSun, (0.392|units.MSun)/((4.0/3.0)*constants.pi*(0.0159 |units.RSun)**3), star.temperature, radius_profile[-250000])
    sound_speed = star.temperature/star.temperature | units.m * units.s**-1
    for i in xrange(len(sound_speed)):
        sound_speed[i] = math.sqrt(((5.0/3.0) * constants.kB * star.temperature[i] / mu()).value_in(units.m **2 * units.s**-2)) | units.m / units.s
    return dict(
        radius = radius_profile.as_quantity_in(units.RSun),
        density = density_profile,
        mass = mass_profile,
        temperature = star.temperature,
        pressure = star.pressure,
        sound_speed = sound_speed,
        cumulative_mass = cumulative_mass_profile,
        tau = tau
    )


def temperature_density_plot(sphGiant, step, outputDir, toPlot = False):
    if not HAS_PYNBODY:
        print "problem plotting"
        return
    width = 5.0 | units.AU
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    
    sphGiant.gasParticles.temperature = 2.0/3.0 * sphGiant.gasParticles.u * mu() / constants.kB
    sphGiant.gasParticles.mu = mu()
    if sphGiant.core.mass > 0.0 | units.MSun:
        star = sph_to_star.convert_SPH_to_stellar_model(sphGiant.gasParticles, core_particle=sphGiant.core, particles_per_zone= 1 )#TODO: surround it by a code which adds the density of the core from mesa.
    else:
        star = sph_to_star.convert_SPH_to_stellar_model(sphGiant.gasParticles)
    data = structure_from_star(star)
    #sphGiant.gasParticles.radius = CalculateVectorSize((sphGiant.gasParticles.x,sphGiant.gasParticles.y,sphGiant.gasParticles.z))
    #data = convert_particles_to_pynbody_data(sphGiant.gasParticles, length_unit, pynbody_unit)
    if toPlot:

        figure = pyplot.figure(figsize = (8, 10))
        pyplot.subplot(1, 1, 1)
        ax = pyplot.gca()
        plotT = semilogy(data["radius"][:-1000], data["temperature"][:-1000], 'r-', label = r'$T(r)$', linewidth=3.0)
        xlabel('Radius', fontsize=24.0)
        ylabel('Temperature', fontsize= 24.0)
        ax.twinx()
        #plotrho = semilogy(data["radius"][:-1000], data["density"][:-1000].as_quantity_in(units.g * units.cm **-3), 'g-', label = r'$\rho(r)$', linewidth=3.0)
        plotrho = semilogy(data["radius"][:-1000], data["density"][:-1000].as_quantity_in(units.g * units.cm **-3), 'g-', label = r'$\rho(r)$', linewidth=3.0)
        plots = plotT + plotrho
        labels = [one_plot.get_label() for one_plot in plots]
        ax.legend(plots, labels, loc=3, fontsize=24.0)
        ax.labelsize=20.0
        ax.titlesize=24.0
        ylabel('Density')
        #print "saved"
        pyplot.legend()
        pyplot.xticks(fontsize=20.0)
        pyplot.yticks(fontsize=20.0)
        pyplot.suptitle('Structure of a {0} star'.format(sphGiant.mass))
        pyplot.savefig(outputDir + "/radial_profile/temperature_radial_proile_{0}".format(step))

        #pyplot.close(figure)
        pyplot.clf()
        pyplot.cla()

        '''
        figure = pyplot.figure(figsize = (15, 11))
        #pyplot.subplot(1, 1,1)
        ax = pyplot.gca()
        pyplot.axes()
        plotC = semilogx(data["radius"][:-1000], (data["cumulative_mass"]/data["mass"][-1])[:-1000], 'r-', label = r'$Mint(r)/Mtot$',linewidth=3.0)
        print (data["radius"])[-1000]
        ax.twinx()
        plotRc= axvline(340.0 | units.RSun, linestyle='dashed', label = r'$Rc$',linewidth=3.0)
        legend = ax.legend(labels=[r'$Mint(r)/Mtot$', r'$Rc$'],ncol=3, loc=4, fontsize= 24.0)
        ax.set_yticklabels([])
        ax.set_ylabel('')
        ax.set_xlabel('Radius [RSun]')
        loc = legend._get_loc()
        print loc
        xlabel('Radius', fontsize=24.0)
        ylabel('')
        ax.set_ylabel('')
        #ylabel('Cumulative Mass to Total Mass Ratio', fontsize=24.0)
        #pyplot.xlim(10,10000)
        pyplot.xlabel('Radius', fontsize=24.0)
        pyplot.xticks(fontsize = 20.0)
        #ax.set_xticklabels([10^1,10^2,10^3,10^4,10^5],fontsize=20)
        pyplot.yticks(fontsize= 20.0)
        pyplot.ylabel('')
        ax.set_ylabel('Cumulative Mass to Total Mass Ratio')
        ax.yaxis.set_label_coords(-0.1,0.5)
        #pyplot.ylabel('Cumulative Mass to Total Mass Ratio')
        #pyplot.axes.labelsize = 24.0
        #pyplot.axes.titlesize = 24.0
        pyplot.legend(bbox_to_anchor=(1.0,0.2),loc=0, fontsize=24.0)
        matplotlib.rcParams.update({'font.size': 20})
        pyplot.tick_params(axis='y', which='both', labelleft='on', labelright='off')
        #pyplot.rc('text', usetex=True)
        #pyplot.suptitle('Cumulative mass ratio of {0} MSun Red Giant Star as a function of the distance from its core'.format(int(sphGiant.mass.value_in(units.MSun) * 100) / 100.0), fontsize=24)
        pyplot.savefig(outputDir + "/radial_profile/cumulative_mass_radial_proile_{0}".format(step))
        '''
        pyplot.close()

    
    #plot to file
    print "writing data to files"
    textFile = open(outputDir + '/radial_profile/temperature_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["temperature"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/density_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["density"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/radius_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["radius"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/sound_speed_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["sound_speed"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/mass_profile{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["mass"]]))
    textFile.close()
    textFile = open(outputDir + '/radial_profile/cumulative_mass_profile{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(y) for y in data["cumulative_mass"]]))
    textFile.close()
    print "claculating values"
    mdot = (4.0 * constants.pi * (340.0 | units.RSun)**2 * GetPropertyAtRadius(data["density"],data["radius"], 340.0 | units.RSun) * GetPropertyAtRadius(data["sound_speed"],data["radius"], 340.0 | units.RSun)).as_quantity_in(units.MSun / units.yr)
    m =  GetPropertyAtRadius(data["cumulative_mass"], data["radius"], 340.0 | units.RSun)
    M =  GetPropertyAtRadius(data["cumulative_mass"], data["radius"], 7000.0 | units.RSun)
    print "Mdot at 340: ", mdot
    print "cs at 340: ",  GetPropertyAtRadius(data["sound_speed"],data["radius"], 3000.0 | units.RSun)
    #print "tau at 3000: ",  GetPropertyAtRadius(data["tau"],data["radius"], 3000.0 | units.RSun)
    print "density at 340: ",  GetPropertyAtRadius(data["density"],data["radius"], 340.0 | units.RSun)
    print "m over 340: ", (M - m)
    print "M total: ", M
    print "time: ", ((M-m)/mdot)

def PlotDensity(sphGiant,core,binary,i, outputDir, vmin, vmax, plotDust=False, dustRadius=700 | units.RSun):
    if not HAS_PYNBODY:
        print "problem plotting"
        return
    figure = pyplot.figure(figsize=(18,18))
    #width = 0.08 * sphGiant.position.lengths_squared().amax().sqrt()
    width = 7.0 * sphGiant.position.lengths_squared().amax().sqrt()
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    pyndata = convert_particles_to_pynbody_data(sphGiant, length_unit, pynbody_unit)
    UnitlessArgs.strip([1]|length_unit, [1]|length_unit)
    cbar = pynbody_sph.image(pyndata, resolution=2000,width=width.value_in(length_unit), units='m_p cm^-2',vmin= vmin, vmax= vmax)
    UnitlessArgs.current_plot = native_plot.gca()
    '''native_plot.xlim(xmax=2, xmin=-10)
    native_plot.ylim(ymax=6, ymin=-6)
    native_plot.xticks([-10,-8,-6,-4,-2,0,2],[-6,-4,-2,0,2,4,6])'''
    native_plot.xlabel('x[AU]')
    native_plot.ylabel('y[AU]')
    #pyplot.xlim(-5,-2)
    #pynbody_column_density_plot(sphGiant, resolution=2000, width=50|units.RSun,vmin= vmin, vmax= vmax,cmap= "hot", fill_nan=True, fill_val=1e25)
    if core.mass != 0 | units.MSun:
        print core.x.as_quantity_in(units.AU), core.y.as_quantity_in(units.AU)
        scatter(core.x, core.y, c="r")
    scatter(binary.x, binary.y, c="w")
    print binary.x.as_quantity_in(units.AU), binary.y.as_quantity_in(units.AU)
    #pyplot.xlim(-930, -350)
    #pyplot.ylim(-190,390)
    if plotDust:
        circle_with_radius(core.x, core.y,dustRadius, fill=False, color='white', linestyle= 'dashed', linewidth=3.0)
    #native_plot.colorbar(fontsize=20.0)
    matplotlib.rcParams.update({'font.size': 36, 'font.family': 'Serif'})
    #pyplot.rc('text', usetex=True)
    #cbar.ax.set_yticklabels(cbar
    # .ax.get_yticklabels(), fontsize=24)
    #pyplot.axes.labelsize(24)
    pyplot.savefig(outputDir + "/plotting_{0}.jpg".format(i))
    pyplot.close()

def PlotVelocity(sphGiant,core,binary,step, outputDir, vmin, vmax):
    if not HAS_PYNBODY:
        print HAS_PYNBODY
        print "problem plotting"
        return
    width = 1.7 * sphGiant.position.lengths_squared().amax().sqrt()
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    pyndata = convert_particles_to_pynbody_data(sphGiant, length_unit, pynbody_unit)
    UnitlessArgs.strip([1]|length_unit, [1]|length_unit)
    pynbody_sph.velocity_image(pyndata, width=width.value_in(length_unit), units='m_p cm^-2',vmin= vmin, vmax= vmax)
    UnitlessArgs.current_plot = native_plot.gca()
    #print core.mass
    #if core.mass != 0 |units.MSun:
    #    scatter(core.x, core.y, c="r")
    scatter(core.x, core.y, c="r")
    scatter(binary.x, binary.y, c="w")
    pyplot.savefig(outputDir + "/velocity/velocity_plotting_{0}.jpg".format(step))
    pyplot.close()

def Plot1Axe(x, fileName, outputDir, timeStep= 1400.0/7000.0, beginTime = 0):
    if len(x) == 0:
        return
    timeLine = [beginTime + time * timeStep for time in xrange(len(x))] | units.day
    native_plot.figure(figsize= (20, 20), dpi= 80)
    plot(timeLine,x)
    xlabel('time[days]')
    native_plot.savefig(outputDir + '/' + fileName + 'time_' + str(beginTime) + "_to_" + str(beginTime + (len(x) - 1.0) * timeStep) + 'days.jpg')
    textFile = open(outputDir + '/' + fileName + 'time_' + str(beginTime) + "_to_" + str(beginTime + (len(x) - 1.0) * timeStep) + 'days.txt', 'w')
    textFile.write(', '.join([str(y) for y in x]))
    textFile.close()

def PlotAdaptiveQuantities(arrayOfValueAndNamePairs, outputDir, beginTime = 0, timeStep= 1400.0/7000.0):
    for a in arrayOfValueAndNamePairs:
        if a[0]:
            Plot1Axe(a[0], a[1], outputDir, timeStep, beginTime)

def PlotEccentricity(eccentricities, outputDir, beginTime = 0, timeStep= 1400.0/7000.0):
    for e in eccentricities:
        if e[0] != []:
            Plot1Axe(e[0], e[1], outputDir, timeStep, beginTime)

def PlotBinaryDistance(distances, outputDir, beginTime = 0, timeStep= 1400.0/7000.0):
    for d in distances:
        if d[0]:
            Plot1Axe(d[0], d[1], outputDir, timeStep, beginTime)

def AnalyzeBinaryChunk(savingDir,gasFiles,dmFiles,outputDir,chunk, vmin, vmax, beginStep, binaryDistances,semmimajors,eccentricities, innerMass, toPlot = False, plotDust=False, dustRadius= 700.0 | units.RSun):
    for i in [j - beginStep for j in chunk]:
        #print "step #",i
        gas_particles_file = os.path.join(os.getcwd(), savingDir,gasFiles[i + beginStep])
        dm_particles_file = None
        if len(dmFiles) > 0:
            dm_particles_file = os.path.join(os.getcwd(),savingDir, dmFiles[i + beginStep])
        #binaryDistances = AdaptingVectorQuantity()
        #eccentricities = []
        sphGiant = SphGiant(gas_particles_file, dm_particles_file, opposite=True)
        try:
            binary = LoadBinaries(dm_particles_file)
            companion = binary[1]
        except: #no binary
            binary = []
            companion = sphGiant
        #print binary
        if len(binary) > 1:
            isBinary= True
            binary = Star(companion, sphGiant)
        else:
            isBinary=False
            binary = Star(sphGiant, sphGiant)
        #print binary.position, binary.vx,binary.vy,binary.vz
        if CalculateVectorSize(CalculateSeparation(sphGiant.core,companion)) < min(sphGiant.core.radius,companion.radius):
            print "merger between companion and the giant! step: ", i + beginStep
            #break

        if isBinary:
            #semmimajor = CalculateSemiMajor(CalculateVelocityDifference(companion, sphGiant.core), CalculateSeparation(companion, sphGiant.core),companion.mass + sphGiant.core.mass).as_quantity_in(units.AU)
            #CalculateEccentricity(companion, sphGiant.core)
            #check if the companion is inside, take into account only the inner mass of the companion's orbit
            sphGiant.CalculateInnerSPH(companion)
            #print "innerGasMass: ", sphGiant.innerGas.mass.value_in(units.MSun)
            innerMass[i] = sphGiant.innerGas.mass.value_in(units.MSun)

            newBinaryVelocityDifference = CalculateVelocityDifference(companion, sphGiant.innerGas)
            newBinarySeparation = CalculateSeparation(companion, sphGiant.innerGas)
            newBinaryMass = companion.mass + sphGiant.innerGas.mass
            newBinarySpecificEnergy = CalculateSpecificEnergy(newBinaryVelocityDifference,newBinarySeparation,sphGiant.innerGas,companion)
            semmimajor = CalculateSemiMajor(newBinaryVelocityDifference, newBinarySeparation, newBinaryMass).as_quantity_in(units.AU)
            eccentricity = CalculateEccentricity(companion, sphGiant.innerGas)
            eccentricities[i] = eccentricity
            binaryDistances[i] = CalculateVectorSize(newBinarySeparation).value_in(units.RSun)
            semmimajors[i] = semmimajor.value_in(units.AU)

            #check if the binary is breaking up
            if newBinarySpecificEnergy > 0 | (units.m **2 / units.s **2):
                print "binary is breaking up", binary.specificEnergy, i

        #temperature_density_plot(sphGiant, i + beginStep , outputDir, toPlot)

        if toPlot:
            PlotDensity(sphGiant.gasParticles,sphGiant.core,companion, i + beginStep , outputDir, vmin, vmax, plotDust= plotDust, dustRadius=dustRadius)
            PlotVelocity(sphGiant.gasParticles,sphGiant.core,companion, i + beginStep, outputDir, vmin, vmax)

    for f in [obj for obj in gc.get_objects() if isinstance(obj,h5py.File)]:
        try:
            f.close()
        except:
            pass

def AnalyzeTripleChunk(savingDir, gasFiles, dmFiles, outputDir, chunk, vmin, vmax, beginStep,
                       binaryDistances, triple1Distances, triple2Distances,
                       aInners, aOuters, aOuters1, aOuters2,
                       eInners, eOuters, eOuters1, eOuters2, inclinations, innerMass, innerMass1, innerMass2, separationTime,
                       toPlot = False, opposite= False):

    for i in [j - beginStep for j in chunk]:
        print i
        gas_particles_file = os.path.join(os.getcwd(), savingDir,gasFiles[i + beginStep])
        dm_particles_file = os.path.join(os.getcwd(),savingDir, dmFiles[i + beginStep])

        sphGiant = SphGiant(gas_particles_file, dm_particles_file, opposite= opposite)

        #binary = Particles(2,pickle.load(open(os.path.join(os.getcwd(),savingDir,"binary.p"),"rb")))
        binary = LoadBinaries(dm_particles_file, opposite= opposite)
        #print binary

        particle1 , particle2 = binary[0] , binary[1]

        innerBinary = Star(particle1,particle2)
        triple1 = Star(particle1, sphGiant)
        triple2 = Star(particle2, sphGiant)

        aInner = CalculateSemiMajor(innerBinary.velocityDifference,innerBinary.separation, innerBinary.mass)
        eInner = CalculateEccentricity(particle1,particle2)

        if CalculateVectorSize(innerBinary.separation) < min(particle1.radius, particle2.radius):
            print "merger between the inner binary!" , innerBinary.separation.as_quantity_in(units.RSun) , i * 1400/7000.0

        if CalculateVectorSize(CalculateSeparation(sphGiant.core,particle1)) < sphGiant.core.radius:
            print "merger between particle1 and the giant!" , i * 1400/7000.0
            #break

        if CalculateVectorSize(CalculateSeparation(sphGiant.core, particle2)) < min(sphGiant.core.radius, particle2.radius):
            print "merger between particle 2 and the giant!" , i * 1400/7000.0
            #break
        #check if the binry is breaking up
        if innerBinary.specificEnergy > 0 | (units.m **2 / units.s **2):
            print "binary is breaking up", innerBinary.specificEnergy , i * 1400/7000.0

        #check if the couple particle1 + giant are breaking up
        if triple1.specificEnergy > 0 | (units.m **2 / units.s **2):
            print "triple1 is breaking up", triple1.specificEnergy , i * 1400/7000.0
            if separationTime == 0:
                separationTime = i * 1400/7000
            #check if the couple particle2 + giant are also breaking up
            if triple2.specificEnergy > 0 | (units.m **2 / units.s **2):
                print "triple2 is also breaking up", triple2.specificEnergy , i * 1400/7000.0
                break

        #check if the couple particle2 + giant are breaking up
        if triple2.specificEnergy > 0 | (units.m **2 / units.s **2):
            print "triple2 is breaking up", triple2.specificEnergy, i * 1400/7000.0
            if separationTime == 0:
                separationTime = i * 1400/7000

        #all the three are connected
        sphGiant.CalculateInnerSPH(innerBinary)
        innerMass[i] = sphGiant.innerGas.mass.value_in(units.MSun)

        tripleMass = innerBinary.mass + sphGiant.innerGas.mass
        tripleVelocityDifference = CalculateVelocityDifference(innerBinary,sphGiant.innerGas)
        tripleSeparation = CalculateSeparation(innerBinary,sphGiant.innerGas)

        aOuter = CalculateSemiMajor(tripleVelocityDifference, tripleSeparation, tripleMass)
        eOuter = CalculateEccentricity(innerBinary,sphGiant.innerGas)

        inclination = CalculateInclination(tripleVelocityDifference, tripleSeparation, innerBinary.velocityDifference, innerBinary.separation)

        binaryDistances[i] = CalculateVectorSize(innerBinary.separation).value_in(units.RSun)

        aInners[i] = aInner.value_in(units.AU)
        aOuters[i] = aOuter.value_in(units.AU)
        eInners[i] = eInner
        eOuters[i] = eOuter
        inclinations[i] = inclination
        innerMass1[i] , aOuters1[i], eOuters1[i], triple1Distances[i] = CalculateBinaryParameters(particle1, sphGiant)
        innerMass2[i] , aOuters2[i], eOuters2[i], triple2Distances[i] = CalculateBinaryParameters(particle2, sphGiant)

        temperature_density_plot(sphGiant, i + beginStep , outputDir, toPlot)
        if toPlot:
            PlotDensity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin, vmax)
            PlotVelocity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin, vmax)

        #close opened handles
        for f in [obj for obj in gc.get_objects() if isinstance(obj,h5py.File)]:
            try:
                f.close()
            except:
                pass

def AnalyzeBinary(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, toPlot = False, plotDust=True, dustRadius=700.0|units.RSun):
    separationTime = 0
    if lastStep == 0 : # no boundary on last step
        lastStep = len(gasFiles)
    print lastStep
    binaryDistances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    semmimajors = multiprocessing.Array('f', [0.0 for i in range(beginStep, lastStep)])
    eccentricities = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    innerMass = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    
    chunkSize = (lastStep - beginStep) / 8
    #chunkSize= (lastStep-beginStep)/(multiprocessing.cpu_count()-6)
    if chunkSize == 0:
        if lastStep - beginStep == 0:
            return
        else:
            chunkSize = 1

    chunks = [xrange(i,i+chunkSize) for i in xrange(beginStep,lastStep,chunkSize)]
    if len(chunks) > 1:
        lastChunkBegin = chunks[-2][-1] + 1
    else:
        lastChunkBegin = 0
    chunks[-1]= xrange(lastChunkBegin,lastStep)

    processes = []
    print chunks
    for chunk in chunks:
        processes.append(multiprocessing.Process(target= AnalyzeBinaryChunk,args=(savingDir,gasFiles,dmFiles,outputDir,
                                                                                  chunk, vmin, vmax, beginStep,
                                                                                  binaryDistances, semmimajors,
                                                                                  eccentricities, innerMass, toPlot,
                                                                                  plotDust,dustRadius,)))
        #pool.map()
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    newBinaryDistances = AdaptingVectorQuantity()
    newSemmimajors = AdaptingVectorQuantity()
    newInnerMass = AdaptingVectorQuantity()
    for j in xrange(len(binaryDistances) - 1):
        newBinaryDistances.append(float(binaryDistances[j]) | units.RSun)
        newSemmimajors.append(float(semmimajors[j]) | units.AU)
        newInnerMass.append(float(innerMass[j]) | units.MSun)
    #print newBinaryDistances
    PlotBinaryDistance([(newBinaryDistances, "InnerBinaryDistances")], outputDir + "/graphs", beginStep)
    PlotAdaptiveQuantities([(newSemmimajors ,"aInners")], outputDir+"/graphs", beginStep)
    PlotEccentricity([(eccentricities, "eInners")], outputDir + "/graphs", beginStep)
    PlotAdaptiveQuantities([(innerMass, "InnerMass")], outputDir + "/graphs", beginStep)



def AnalyzeTriple(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, toPlot = False, opposite= False):
    separationTime = multiprocessing.Value('f')
    if lastStep == 0 : # no boundary on last step
        lastStep = len(dmFiles)
    print lastStep

    binaryDistances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    triple1Distances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    triple2Distances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    aInners = multiprocessing.Array('f', [0.0 for i in range(beginStep, lastStep)])
    aOuters = multiprocessing.Array('f', [0.0 for i in range(beginStep, lastStep)])
    aOuters1 = multiprocessing.Array('f', [0.0 for i in range(beginStep, lastStep)]) # for the couple particle1 + giant
    aOuters2 = multiprocessing.Array('f', [0.0 for i in range(beginStep, lastStep)]) # for the couple particle2 + giant
    eInners = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    eOuters = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    eOuters1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)]) # for the couple particle1 + giant
    eOuters2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)]) # for the couple particle2 + giant
    inclinations = multiprocessing.Array('f', range(beginStep, lastStep))
    innerMass = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    innerMass1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    innerMass2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])

    chunkSize= (lastStep-beginStep)/(multiprocessing.cpu_count() - 6)
    if chunkSize == 0:
        if lastStep - beginStep == 0:
            return
        else:
            chunkSize = 1

    chunks = [xrange(i,i+chunkSize) for i in xrange(beginStep,lastStep,chunkSize)]
    if len(chunks) > 1:
        lastChunkBegin = chunks[-2][-1] + 1
    else:
        lastChunkBegin = beginStep
    chunks[-1] = xrange(lastChunkBegin, lastStep)
    processes = []
    print chunks
    for chunk in chunks:
        processes.append(multiprocessing.Process(target= AnalyzeTripleChunk,args=(savingDir, gasFiles, dmFiles, outputDir, chunk, vmin, vmax, beginStep,
                       binaryDistances, triple1Distances, triple2Distances,
                       aInners, aOuters, aOuters1, aOuters2,
                       eInners, eOuters, eOuters1, eOuters2, inclinations, innerMass, innerMass1, innerMass2, separationTime, toPlot, opposite, )))
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    newBinaryDistances = AdaptingVectorQuantity()
    newTriple1Distances = AdaptingVectorQuantity()
    newTriple2Distances = AdaptingVectorQuantity()
    newAInners = AdaptingVectorQuantity()
    newAOuters = AdaptingVectorQuantity()
    newAOuters1 = AdaptingVectorQuantity()
    newAOuters2 = AdaptingVectorQuantity()
    newInnerMass = AdaptingVectorQuantity()
    newInnerMass1 = AdaptingVectorQuantity()
    newInnerMass2 = AdaptingVectorQuantity()

    for j in xrange(len(binaryDistances)-1):
        newBinaryDistances.append(float(binaryDistances[j]) | units.RSun)
        newTriple1Distances.append(float(triple1Distances[j]) | units.RSun)
        newTriple2Distances.append(float(triple2Distances[j]) | units.RSun)
        newAInners.append(float(aInners[j]) | units.AU)
        newAOuters.append(float(aOuters[j]) | units.AU)
        newAOuters1.append(float(aOuters1[j]) | units.AU)
        newAOuters2.append(float(aOuters2[j]) | units.AU)
        newInnerMass.append(float(innerMass[j]) | units.MSun)
        newInnerMass1.append(float(innerMass1[j]) | units.MSun)
        newInnerMass2.append(float(innerMass2[j]) | units.MSun)

    PlotBinaryDistance([(newBinaryDistances, "InnerBinaryDistances"), (newTriple1Distances, "triple1Distances"),
                        (newTriple2Distances, "triple2Distances")], outputDir + "/graphs", beginStep)
    PlotAdaptiveQuantities([(newAInners,"aInners"),(newAOuters, "aOuters")], outputDir+"/graphs")
    PlotAdaptiveQuantities([(newAOuters1, "aOuters1"), (newAOuters2, "aOuters2")], outputDir+ "/graphs", separationTime)
    PlotEccentricity([(eInners, "eInners"), (eOuters, "eOuters")], outputDir + "/graphs", beginStep)
    PlotEccentricity([(eOuters1, "eOuters1"), (eOuters2, "eOuters2")],outputDir + "/graphs", separationTime)
    Plot1Axe(inclinations,"inclinations", outputDir+"/graphs", beginTime=beginStep)
    PlotAdaptiveQuantities([(innerMass, "InnerMass"), (innerMass1, "InnerMass1"), (innerMass2, "InnerMass2")], outputDir + "/graphs", beginStep)

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
    if len(args) > 4:
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
        plot = bool(int(args[7]))
    else:
        plot = False
    if len(args) >8:
        opposite = True
    else:
        opposite = False
    outputDir = savingDir + "/pics"
    return savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, plot, opposite

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


def main(args= ["../../BIGDATA/code/amuse-10.0/runs200000/run_003","evolution",0,1e16,1e34, 1]):
    savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, plot, opposite = GetArgs(args)
    print "plotting to " +  outputDir + " plot- " + str(plot) +  " from " +  savingDir +" begin step = " , beginStep , \
        " vmin, vmax = " , vmin, vmax, "special comparing = ", toCompare
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
        AnalyzeBinary(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, plot, plotDust=False)
    elif numberOfCompanion ==3: #triple
        AnalyzeTriple(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, plot, opposite)

if __name__ == "__main__":
    for arg in sys.argv:
        print arg
    print len(sys.argv)
    main(sys.argv)
