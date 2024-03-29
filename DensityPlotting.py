import os
import time
import os.path
import functools
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
import numpy
matplotlib.use('Agg')
from ctypes import *
from amuse.units import units, constants, nbody_system, quantities
from amuse.units import *

#from amuse.lab import *
from amuse.units.quantities import AdaptingVectorQuantity, VectorQuantity
from amuse.datamodel import Particles, Particle
from amuse.ext import sph_to_star
from amuse.io import write_set_to_file, read_set_from_file

from amuse.plot import *
    #scatter, xlabel, ylabel, plot, pynbody_column_density_plot, HAS_PYNBODY, _smart_length_units_for_pynbody_data, convert_particles_to_pynbody_data, UnitlessArgs, semilogx, semilogy, loglog, xlabel, ylabel

from matplotlib import pyplot
import pynbody
import pynbody.plot.sph as pynbody_sph
from pynbody.analysis import angmom
from amuse.plot import *
#scatter, xlabel, ylabel, plot, native_plot, sph_particles_plot, circle_with_radius, axvline
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
        particles = Particles()
        part1=particle1.copy()
        particles.add_particle(part1)
        part2 = Particle()
        part2.mass = particle2.mass
        part2.position = particle2.position
        part2.velocity = particle2.velocity
        part2.radius = particle2.radius
        particles.add_particle(part2)
        self.velocity = particles.center_of_mass_velocity()
        self.vx = self.velocity[0]
        self.vy = self.velocity[1]
        self.vz = self.velocity[2]
        self.position = particles.center_of_mass()
        self.x = self.position[0]
        self.y = self.position[1]
        self.z = self.position[2]


        self.mass  = particles.total_mass()
        self.velocityDifference = CalculateVelocityDifference(particle1,particle2)
        self.separation = CalculateSeparation(particle1,particle2)
        self.specificEnergy = CalculateSpecificEnergy(self.velocityDifference,self.separation,particle1,particle2)
        print(("inner specific energy: ", self.specificEnergy))
        self.potentialEnergy = particles.potential_energy()
        self.kineticEnergy = particles.kinetic_energy()
        particles.move_to_center()
        self.angularMomentum = particles.total_angular_momentum()
        self.omega = CalculateOmega(particles)




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
        self.gas.velocity = self.gasParticles.center_of_mass_velocity()

        #self.gas.vx, self.gas.vy, self.gas.vz = self.gasParticles.center_of_mass_velocity()
        self.gas.v = self.gas.velocity
        self.mass = self.gas.mass + self.core.mass
        self.position = (self.gas.position * self.gas.mass + self.core.position* self.core.mass)/self.mass
        self.velocity = (self.gas.velocity * self.gas.mass + self.core.velocity* self.core.mass)/self.mass
        self.x , self.y, self.z = self.position
        self.vx, self.vy, self.vz = self.velocity
        self.v = self.velocity
        self.radius = self.gasParticles.total_radius()
        self.dynamicalTime = 1.0/(constants.G*self.mass/((4*constants.pi*self.radius**3)/3))**0.5
        self.kineticEnergy = 0.0 |units.kg*(units.km**2) / units.s**2
        self.thermalEnergy = 0.0 |units.kg*(units.km**2) / units.s**2
        self.potentialEnergy = 0.0 |units.kg*(units.km**2) / units.s**2
        self.gasPotential= 0.0 | units.kg * (units.km ** 2) / units.s ** 2
        self.gasKinetic = 0.0 | units.kg * (units.km ** 2) / units.s ** 2
        self.omegaPotential = 0.0 | units.kg * (units.km ** 2) / units.s ** 2
        #self.angularMomentum = totalGiant.total_angular_momentum()

    def CalculateEnergies(self,comV=None):
        self.gasKinetic = self.gasParticles.kinetic_energy()
        self.coreKinetic = 0.5 * self.core.mass * (CalculateVectorSize(self.core.velocity))**2
        self.kineticEnergy = self.gasKinetic + self.coreKinetic
        self.thermalEnergy = self.gasParticles.thermal_energy()
        print(("giant kinetic: ", self.kineticEnergy))
        print(("giant thermal: ", self.thermalEnergy))
        self.gasPotential = self.GasPotentialEnergy()
        print(("gas potential: ", self.gasPotential))
        self.potentialEnergy = self.gasPotential + self.potentialEnergyWithParticle(self.core, 0.0 | units.m)
        #self.potentialEnergy = self.gasPotential + self.potentialEnergyWithParticle(self.core, self.core.radius/2.8)
        print(("giant potential: ", self.potentialEnergy))
        #print "potential energies: ", self.gasPotential, self.gasParticles.mass[-1]*self.gas.mass*constants.G/self.radius
        #self.potentialEnergy = self.gasPotential + self.potentialEnergyWithParticle(self.core)

    def GasPotentialEnergy(self):
        return self.gasParticles.potential_energy()
        self.gasPotential = 0.0 |units.kg*(units.m**2) / units.s**2
        mass = self.gasParticles.mass
        x_vector = self.gasParticles.x
        y_vector = self.gasParticles.y
        z_vector = self.gasParticles.z
        epsilon = self.gasParticles.epsilon
        for i in range(len(self.gasParticles) - 1):
            x = x_vector[i]
            y = y_vector[i]
            z = z_vector[i]
            dx = x - x_vector[i + 1:]
            dy = y - y_vector[i + 1:]
            dz = z - z_vector[i + 1:]
            dr_squared = (dx * dx) + (dy * dy) + (dz * dz)
            dr = (dr_squared + (epsilon[i+1:]/2.8)**2).sqrt()
            m_m = mass[i] * mass[i + 1:]

            energy_of_this_particle = constants.G * ((m_m / dr).sum())
            self.gasPotential -= energy_of_this_particle

        return self.gasPotential

    def potentialEnergyWithParticle(self,particle, epsilon = None):
        energy = 0.0 | units.kg*(units.m**2) / units.s**2
        for part in self.gasParticles:
            if epsilon is not None:
                energy += -1.0*constants.G*part.mass*particle.mass/(CalculateVectorSize(CalculateSeparation(particle,part))**2+epsilon**2)**0.5
            else:
                energy += -1.0*constants.G*part.mass*particle.mass/(CalculateVectorSize(CalculateSeparation(particle,part))**2+part.epsilon**2)**0.5
        return energy


    def gravityWithParticle(self,particle):
        force = VectorQuantity([0.0,0.0,0.0],units.kg*units.km*units.s**-2)
        for part in self.gasParticles:
            f = -1.0 * constants.G * part.mass * particle.mass / (
                    (CalculateVectorSize(CalculateSeparation(particle, part)) ** 2) ** 0.5) ** 3
            force[0] += f * (part.x-particle.x)
            force[1] += f * (part.y - particle.y)
            force[2] += f * (part.z - particle.z)


        f = -1.0 * constants.G * part.mass * particle.mass / (
                (CalculateVectorSize(CalculateSeparation(particle, self.core)) ** 2) ** 0.5) ** 3
        force[0] += f * (self.core.x-particle.x)
        force[1] += f * (self.core.y - particle.y)
        force[2] += f * (self.core.z - particle.z)

        return force

    def GetAngularMomentum(self,comPos=None,comV=None):
        totalGiant = Particles()
        totalGiant.add_particles(self.gasParticles)
        totalGiant.add_particle(self.core)
        totGiant = totalGiant.copy()
        if comPos is not None:
            totGiant.position -= comPos
        if comV is not None:
            totGiant.velocity -= comV
        self.omegaPotential = CalculateOmega(totGiant)
        return totGiant.total_angular_momentum()

    def GetAngularMomentumOfGas(self, comPos=None, comV=None):
        gas = self.gasParticles.copy()

        if comPos is not None:
            gas.position -= comPos
        if comV is not None:
            gas.velocity -= comV

        return gas.total_angular_momentum()


    def CalculateInnerSPH(self, relativeParticle, localRadius=50.0 | units.RSun, com_position=[0.0,0.0,0.0] | units.m,
                          com_velocity = [0.0,0.0,0.0] | units.m / units.s):
        self.innerGas = Star(None, None)
        radius = CalculateVectorSize(CalculateSeparation(relativeParticle, self.core))
        print((time.ctime(), "beginning inner gas calculation"))
        self.CalculateSphMassVelocityAndPositionInsideRadius(radius, includeCore=True, centeralParticle=relativeParticle,
                                                             localRadius=localRadius, com_position_for_angular_momenta=com_position,
                                                             com_velocity_for_angular_momenta=com_velocity)
        self.innerGas.x , self.innerGas.y, self.innerGas.z = self.innerGas.position
        self.innerGas.kineticEnergy = 0.5*self.innerGas.mass*CalculateVectorSize(self.innerGas.v)**2

        print((time.ctime(), "calculated!"))
    def CalculateTotalGasMassInsideRadius(self, radius):
        innerMass = self.core.mass
        for particle in self.gasParticles:
            separation = CalculateVectorSize(CalculateSeparation(particle, self.core))
            if separation < radius:
                innerMass += particle.mass
        return innerMass

    def CalculateSphMassVelocityAndPositionInsideRadius(self,radius,includeCore=True,centeralParticle=None,
                                                        localRadius=0.0 | units.RSun,
                                                        com_position_for_angular_momenta=[0.0,0.0,0.0] | units.m,
                          com_velocity_for_angular_momenta = [0.0,0.0,0.0] | units.m / units.s):

        self.innerGas.vxTot , self.innerGas.vyTot , self.innerGas.vzTot = ( 0.0 , 0.0, 0.0 )| units.m * units.s**-1
        self.innerGas.xTot , self.innerGas.yTot , self.innerGas.zTot = ( 0.0 , 0.0, 0.0 )| units.m
        self.innerGas.lxTot, self.innerGas.lyTot, self.innerGas.lzTot = (0.0, 0.0, 0.0) | (units.g * units.m**2 * units.s ** -1)

        self.localMass = 0.0 | units.MSun
        if includeCore:
            self.innerGas.mass = self.core.mass
            cmass = self.core.mass.value_in(units.MSun)
            vx = self.core.vx
            vy= self.core.vy
            vz = self.core.vz
            x = self.core.x
            y = self.core.y
            z = self.core.z
        else:
            cmass = 0.0 | units.MSun
            vx = 0.0 | units.m / units.s
            vy= 0.0 | units.m / units.s
            vz = 0.0 | units.m / units.s
            x = 0.0 | units.AU
            y = 0.0 | units.AU
            z = 0.0 | units.AU

        velocityAndMass = [vx * cmass, vy* cmass, vz * cmass]
        positionAndMass = [x * cmass, y * cmass, z * cmass]
        angularmomentum = CalculateSpecificMomentum((x,y,z),(vx,vy,vz))
        if cmass != 0.0:
            angularmomentum = [l*(cmass |units.MSun) for l in angularmomentum]

        particlesAroundCore = 0
        particlesAroundCenteral = 0
        i = 0
        for particle in self.gasParticles:
            #print i
            i += 1
            separationFromCore = CalculateVectorSize(CalculateSeparation(particle, self.core))
            if separationFromCore < radius:
                pmass = particle.mass.value_in(units.MSun)
                self.innerGas.mass += particle.mass
                velocityAndMass[0] += particle.vx * pmass
                velocityAndMass[1] += particle.vy * pmass
                velocityAndMass[2] += particle.vz * pmass
                positionAndMass[0] += particle.x * pmass
                positionAndMass[1] += particle.y * pmass
                positionAndMass[2] += particle.z * pmass
                angularmomentumOfParticle = CalculateSpecificMomentum(particle.position-com_position_for_angular_momenta,
                                                                      particle.velocity-com_velocity_for_angular_momenta)
                angularmomentum[0] += angularmomentumOfParticle[0] * particle.mass
                angularmomentum[1] += angularmomentumOfParticle[1] * particle.mass
                angularmomentum[2] += angularmomentumOfParticle[2] * particle.mass
                particlesAroundCore += 1

            if centeralParticle != None:
                separationFromCentral = CalculateVectorSize(CalculateSeparation(particle, centeralParticle))
                if separationFromCentral < localRadius:
                    self.localMass += particle.mass
                    particlesAroundCenteral += 1

        print((time.ctime(), particlesAroundCore, particlesAroundCenteral))
        if particlesAroundCore > 0:
            totalMass=  self.innerGas.mass.value_in(units.MSun)
            self.innerGas.vxTot = velocityAndMass[0] / totalMass
            self.innerGas.vyTot = velocityAndMass[1] / totalMass
            self.innerGas.vzTot = velocityAndMass[2] / totalMass

            self.innerGas.xTot = positionAndMass[0] / totalMass
            self.innerGas.yTot = positionAndMass[1] / totalMass
            self.innerGas.zTot = positionAndMass[2] / totalMass

            self.innerGas.lxTot = angularmomentum[0]
            self.innerGas.lyTot = angularmomentum[1]
            self.innerGas.lzTot = angularmomentum[2]

        self.innerGas.v = (self.innerGas.vxTot, self.innerGas.vyTot, self.innerGas.vzTot)
        self.innerGas.position = (self.innerGas.xTot, self.innerGas.yTot, self.innerGas.zTot)
        self.innerGas.angularMomentum =  (self.innerGas.lxTot, self.innerGas.lyTot, self.innerGas.lzTot)

        if particlesAroundCenteral > 0:
            self.localDensity = self.localMass / ((4.0*constants.pi*localRadius**3)/3.0)
        else:
            self.localDensity = 0.0 | units.g / units.m**3

    def CountLeavingParticlesInsideRadius(self, com_position= [0.0,0.0,0.0] | units.m,
                                          com_velocity=[0.0,0.0,0.0] | units.m / units.s, companion = None, method="estimated"):
        self.leavingParticles = 0
        self.totalUnboundedMass = 0 | units.MSun
        dynamicalVelocity= self.radius/self.dynamicalTime
        particlesExceedingMaxVelocity = 0
        velocityLimitMax = 0.0 | units.cm/units.s
        gas = self.gasParticles.copy()
        gas.position -= com_position
        gas.velocity -= com_velocity
        specificKinetics = gas.specific_kinetic_energy()
        com_particle = Particle(mass=self.mass)
        com_particle.position = com_position
        com_particle.velocity = com_velocity
        extra_potential = [0.0 | units.erg / units.g for particle in  self.gasParticles]
        if companion is not None:
            com_particle.mass += companion.mass
            #com_particle.mass -= self.core.mass
            extra_potential = [CalculatePotentialEnergy(particle, companion) / particle.mass for particle in
                               self.gasParticles]
        print(("using method ", method))
        if method == "estimated":
            specificEnergy = [CalculateSpecificEnergy(particle.velocity - com_velocity, particle.position - com_position,
                                                     particle, com_particle) for particle in self.gasParticles]
        else:
            self.CalculateGasSpecificPotentials()
            print("calculated potentials for gas")
            specificEnergy = [self.gasSpesificPotentials[i] + CalculatePotentialEnergy(self.gasParticles[i],
                                                                                          self.core) / self.gasParticles[i].mass \
                                 + extra_potential[i] + specificKinetics[i] for i in range(len(self.gasParticles))]

        for i, particle in enumerate(self.gasParticles):
            volume = (4.0 / 3.0) * constants.pi * particle.radius ** 3
            particleSoundSpeed = ((5.0 / 3.0) * particle.pressure / (particle.mass / volume)) ** 0.5
            velocityLimit = min(dynamicalVelocity, particleSoundSpeed)
            velocityLimitMax = max(velocityLimitMax,velocityLimit)
            if CalculateVectorSize(particle.velocity) > velocityLimit:
                particlesExceedingMaxVelocity += 1

            if specificEnergy[i] > 0 | specificEnergy[i].unit:
                self.leavingParticles += 1
                self.totalUnboundedMass += particle.mass

        print(("over speed ", particlesExceedingMaxVelocity*100.0 / len(self.gasParticles), "limit: ", velocityLimitMax))

        return self.leavingParticles
    def CalculateGasSpecificPotentials(self):
        n = len(self.gasParticles)

        max = 100000 * 100  # 100m floats
        block_size = max // n
        if block_size == 0:
            block_size = 1  # if more than 100m particles, then do 1 by one
        mass = self.gasParticles.mass
        x_vector = self.gasParticles.x
        y_vector = self.gasParticles.y
        z_vector = self.gasParticles.z

        potentials = VectorQuantity.zeros(len(mass), mass.unit / x_vector.unit)
        inf_len = numpy.inf | x_vector.unit
        offset = 0
        newshape = (n, 1)
        x_vector_r = x_vector.reshape(newshape)
        y_vector_r = y_vector.reshape(newshape)
        z_vector_r = z_vector.reshape(newshape)
        mass_r = mass.reshape(newshape)
        while offset < n:
            if offset + block_size > n:
                block_size = n - offset
            x = x_vector[offset:offset + block_size]
            y = y_vector[offset:offset + block_size]
            z = z_vector[offset:offset + block_size]
            indices = numpy.arange(block_size)
            dx = x_vector_r - x
            dy = y_vector_r - y
            dz = z_vector_r - z
            dr_squared = (dx * dx) + (dy * dy) + (dz * dz)
            dr = (dr_squared).sqrt()
            index = (indices + offset, indices)
            dr[index] = inf_len
            potentials += (mass[offset:offset + block_size] / dr).sum(axis=1)
            offset += block_size

        self.gasSpesificPotentials = -constants.G * potentials

    def FindSmallestCell(self):
        smallestRadius = self.gasParticles.total_radius()
        for gasParticle in self.gasParticles:
            if gasParticle.radius < smallestRadius:
                smallestRadius = gasParticle.radius
        return smallestRadius

    def FindLowestNumberOfNeighbours(self):
        numberOfNeighbours = len(self.gasParticles)
        for gasParticle in self.gasParticles:
            if gasParticle.num_neighbours < numberOfNeighbours:
                numberOfNeighbours = gasParticle.num_neighbours
        return numberOfNeighbours



    def CalculateQuadropoleMoment(self):
        Qxx = (self.core.mass * (self.core.ax*self.core.x + 2 * self.core.vx * self.core.vx +
                                        self.core.x * self.core.ax - (2.0/3.0) * (self.core.ax * self.core.x +
                                                                                      self.core.ay * self.core.y +
                                                                                      self.core.az * self.core.z +
                                                                                      CalculateVectorSize(self.core.velocity)**2)))
        Qxy = (self.core.mass * (self.core.ax * self.core.y + 2 * self.core.vx * self.core.vy +
                                            self.core.x * self.core.ay))
        Qxz = (self.core.mass * (self.core.ax * self.core.z + 2 * self.core.vx * self.core.vz +
                                            self.core.x * self.core.az))
        Qyx  = (self.core.mass * (self.core.ay * self.core.x + 2 * self.core.vy * self.core.vx +
                                            self.core.y * self.core.ax))
        Qyy = (self.core.mass * (self.core.ay*self.core.y + 2 * self.core.vy * self.core.vy +
                                            self.core.y * self.core.ay - (2.0/3.0) * (self.core.ax * self.core.x +
                                                                                          self.core.ay * self.core.y +
                                                                                          self.core.az * self.core.z +
                                                                                          CalculateVectorSize(self.core.velocity)**2)))
        Qyz = (self.core.mass * (self.core.ay * self.core.z + 2 * self.core.vy * self.core.vz +
                                            self.core.y * self.core.az))
        Qzx = (self.core.mass * (self.core.az * self.core.x + 2 * self.core.vz * self.core.vx +
                                            self.core.z * self.core.ax))
        Qzy = (self.core.mass * (self.core.az * self.core.y + 2 * self.core.vz * self.core.vy +
                                            self.core.z * self.core.ay))
        Qzz = (self.core.mass * (self.core.az * self.core.z + 2 * self.core.vz * self.core.vz +
                                            self.core.z * self.core.az - (2.0/3.0) * (self.core.ax * self.core.x +
                                                                                          self.core.ay * self.core.y +
                                                                                          self.core.az * self.core.z +
                                                                                          CalculateVectorSize(self.core.velocity)**2)))
        for gasParticle in self.gasParticles:
            Qxx += (gasParticle.mass * (gasParticle.ax*gasParticle.x + 2 * gasParticle.vx * gasParticle.vx +
                                        gasParticle.x * gasParticle.ax - (2.0/3.0) * (gasParticle.ax * gasParticle.x +
                                                                                      gasParticle.ay * gasParticle.y +
                                                                                      gasParticle.az * gasParticle.z +
                                                                                      CalculateVectorSize(gasParticle.velocity)**2)))
            Qxy += (gasParticle.mass * (gasParticle.ax * gasParticle.y + 2 * gasParticle.vx * gasParticle.vy +
                                            gasParticle.x * gasParticle.ay))
            Qxz += (gasParticle.mass * (gasParticle.ax * gasParticle.z + 2 * gasParticle.vx * gasParticle.vz +
                                            gasParticle.x * gasParticle.az))
            Qyx += (gasParticle.mass * (gasParticle.ay * gasParticle.x + 2 * gasParticle.vy * gasParticle.vx +
                                            gasParticle.y * gasParticle.ax))
            Qyy += (gasParticle.mass * (gasParticle.ay*gasParticle.y + 2 * gasParticle.vy * gasParticle.vy +
                                            gasParticle.y * gasParticle.ay - (2.0/3.0) * (gasParticle.ax * gasParticle.x +
                                                                                          gasParticle.ay * gasParticle.y +
                                                                                          gasParticle.az * gasParticle.z +
                                                                                          CalculateVectorSize(gasParticle.velocity)**2)))
            Qyz += (gasParticle.mass * (gasParticle.ay * gasParticle.z + 2 * gasParticle.vy * gasParticle.vz +
                                            gasParticle.y * gasParticle.az))
            Qzx += (gasParticle.mass * (gasParticle.az * gasParticle.x + 2 * gasParticle.vz * gasParticle.vx +
                                            gasParticle.z * gasParticle.ax))
            Qzy += (gasParticle.mass * (gasParticle.az * gasParticle.y + 2 * gasParticle.vz * gasParticle.vy +
                                            gasParticle.z * gasParticle.ay))
            Qzz += (gasParticle.mass * (gasParticle.az * gasParticle.z + 2 * gasParticle.vz * gasParticle.vz +
                                            gasParticle.z * gasParticle.az - (2.0/3.0) * (gasParticle.ax * gasParticle.x +
                                                                                          gasParticle.ay * gasParticle.y +
                                                                                          gasParticle.az * gasParticle.z +
                                                                                          CalculateVectorSize(gasParticle.velocity)**2)))


        return Qxx.value_in(units.m**2 * units.kg * units.s**-2),Qxy.value_in(units.m**2 * units.kg * units.s**-2),\
               Qxz.value_in(units.m**2 * units.kg * units.s**-2),Qyx.value_in(units.m**2 * units.kg * units.s**-2),\
               Qyy.value_in(units.m**2 * units.kg * units.s**-2),Qyz.value_in(units.m**2 * units.kg * units.s**-2),\
               Qzx.value_in(units.m**2 * units.kg * units.s**-2),Qzy.value_in(units.m**2 * units.kg * units.s**-2),\
               Qzz.value_in(units.m**2 * units.kg * units.s**-2)

class MultiProcessArrayWithUnits:
    def __init__(self,size,units):
        self.array = multiprocessing.Array('f', [-1.0 for i in range(size)])
        self.units = units

    def plot(self, filename, outputDir,timeStep, beginStep, toPlot):
        if self.units is None:
            array = [a for a in self.array]
        else:
            array = AdaptingVectorQuantity([a for a in self.array], self.units)

        Plot1Axe(array,filename, outputDir,timeStep, beginStep, toPlot)

def LoadBinaries(file, opposite= False):
    load = read_set_from_file(file, format='amuse')
    #print load
    if not opposite:
        stars = Particles(2, particles= [load[0], load[1]])
    else: #take the next
        stars = Particles(2, particles= [load[1], load[2]])
    return stars

def CalculateQuadropoleMomentOfParticle(particle):
    Qxx = (particle.mass * (particle.ax*particle.x + 2 * particle.vx * particle.vx +
                                    particle.x * particle.ax - (2.0/3.0) * (particle.ax * particle.x +
                                                                                  particle.ay * particle.y +
                                                                                  particle.az * particle.z +
                                                                                  CalculateVectorSize(particle.velocity)**2))).value_in(units.m**2 * units.kg * units.s**-2)
    Qxy = (particle.mass * (particle.ax * particle.y + 2 * particle.vx * particle.vy +
                                    particle.x * particle.ay)).value_in(units.m**2 * units.kg * units.s**-2)
    Qxz = (particle.mass * (particle.ax * particle.z + 2 * particle.vx * particle.vz +
                                    particle.x * particle.az)).value_in(units.m**2 * units.kg * units.s**-2)
    Qyx  = (particle.mass * (particle.ay * particle.x + 2 * particle.vy * particle.vx +
                                    particle.y * particle.ax)).value_in(units.m**2 * units.kg * units.s**-2)
    Qyy = (particle.mass * (particle.ay*particle.y + 2 * particle.vy * particle.vy +
                                    particle.y * particle.ay - (2.0/3.0) * (particle.ax * particle.x +
                                                                                  particle.ay * particle.y +
                                                                                  particle.az * particle.z +
                                                                                  CalculateVectorSize(particle.velocity)**2))).value_in(units.m**2 * units.kg * units.s**-2)
    Qyz = (particle.mass * (particle.ay * particle.z + 2 * particle.vy * particle.vz +
                                    particle.y * particle.az)).value_in(units.m**2 * units.kg * units.s**-2)
    Qzx = (particle.mass * (particle.az * particle.x + 2 * particle.vz * particle.vx +
                                    particle.z * particle.ax)).value_in(units.m**2 * units.kg * units.s**-2)
    Qzy = (particle.mass * (particle.az * particle.y + 2 * particle.vz * particle.vy +
                                    particle.z * particle.ay)).value_in(units.m**2 * units.kg * units.s**-2)
    Qzz = (particle.mass * (particle.az * particle.z + 2 * particle.vz * particle.vz +
                                    particle.z * particle.az - (2.0/3.0) * (particle.ax * particle.x +
                                                                                  particle.ay * particle.y +
                                                                                  particle.az * particle.z +
                                                                                  CalculateVectorSize(particle.velocity)**2))).value_in(units.m**2 * units.kg * units.s**-2)
    return Qxx,Qxy,Qxz,Qyx,Qyy,Qyz,Qzx,Qzy,Qzz

def GetPropertyAtRadius(mesaStarPropertyProfile, mesaStarRadiusProfile, radius):
    profileLength = len(mesaStarRadiusProfile)
    i = 0
    while i < profileLength and mesaStarRadiusProfile[i] < radius:
        i += 1
    return mesaStarPropertyProfile[min(i, profileLength - 1)]


def CalculateCumulantiveMass(densityProfile, radiusProfile):
    profileLength = len(radiusProfile)
    cmass = [densityProfile[0] * 4.0/3.0 * constants.pi * radiusProfile[0] ** 3 for i in range(profileLength)]
    for i in range(1, profileLength):
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
    tauPoint = [kappa * densityProfile[i] * (radiusProfile[i+1] - radiusProfile[i]) for i in range(0, radiusIndex)]
    tauPoint.append((0.0 |(units.g*units.cm**-2))*kappa)
    tau = tauPoint
    tau[radiusIndex] = tauPoint[radiusIndex]
    for i in range(radiusIndex - 1, 0 , -1 ):
        tau[i] = tau[i + 1] + tauPoint[i]
    #print tau[-1], tau[-100]
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
        print("Error in calculating mu: mass fractions do not sum to 1.0")
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
    tau = CalculateTau(density_profile, radius_profile, 0.0159 | units.RSun, (0.392|units.MSun)/((4.0/3.0)*constants.pi*(0.0159 |units.RSun)**3), star.temperature, radius_profile[-100])
    sound_speed = star.temperature / star.temperature | units.cm / units.s
    for i in range(len(star.temperature)):
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

def velocity_softening_distribution(sphGiant,step,outputDir):
    sorted = sphGiant.gasParticles.pressure.argsort()[::-1]
    binned = sorted.reshape((-1, 1))
    velocities = sphGiant.gasParticles.velocity[binned].sum(axis=1)
    textFile = open(outputDir + '/radial_profile/velocities_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(CalculateVectorSize(v)) for v in velocities]))
    textFile.close()
    h = sphGiant.gasParticles.radius[binned].sum(axis=1)
    textFile = open(outputDir + '/radial_profile/softenings_{0}'.format(step) + '.txt', 'w')
    textFile.write(', '.join([str(r) for r in h]))
    textFile.close()

def temperature_density_plot(sphGiant, step, outputDir, toPlot = False, plotDust= False, dustRadius= 0.0 | units.RSun):
    if not HAS_PYNBODY:
        print("problem plotting")
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

    #plot to file
    print("writing data to files")
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
    velocity_softening_distribution(sphGiant,step,outputDir)
    if toPlot:
        figure = pyplot.figure(figsize = (8, 10))
        pyplot.subplot(1, 1, 1)
        ax = pyplot.gca()
        plotT = semilogy(data["radius"], data["temperature"], 'r-', label = r'$T(r)$', linewidth=3.0)
        xlabel('Radius', fontsize=24.0)
        ylabel('Temperature', fontsize= 24.0)
        ax.twinx()
        #plotrho = semilogy(data["radius"][:-1000], data["density"][:-1000].as_quantity_in(units.g * units.cm **-3), 'g-', label = r'$\rho(r)$', linewidth=3.0)
        plotrho = semilogy(data["radius"], data["density"].as_quantity_in(units.g * units.cm **-3), 'g-', label = r'$\rho(r)$', linewidth=3.0)
        plots = plotT + plotrho
        labels = [one_plot.get_label() for one_plot in plots]
        ax.legend(plots, labels, loc=3)
        ax.labelsize=20.0
        ax.titlesize=24.0
        ylabel('Density')
        #print "saved"
        pyplot.legend()
        pyplot.xticks(fontsize=20.0)
        pyplot.yticks(fontsize=20.0)
        pyplot.suptitle('Structure of a {0} star'.format(sphGiant.mass))
        pyplot.savefig(outputDir + "/radial_profile/temperature_radial_proile_{0}.jpg".format(step), format='jpeg')

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

    
    if plotDust:
        print("calculating values")

        mdot = (4.0 * constants.pi * (dustRadius)**2 * GetPropertyAtRadius(data["density"],data["radius"], dustRadius) * GetPropertyAtRadius(data["sound_speed"],data["radius"],dustRadius)).as_quantity_in(units.MSun / units.yr)
        m =  GetPropertyAtRadius(data["cumulative_mass"], data["radius"], dustRadius)
        M =  GetPropertyAtRadius(data["cumulative_mass"], data["radius"], 7000.0 | units.RSun)
        print(("Mdot at 340: ", mdot))
        print(("cs at 340: ",  GetPropertyAtRadius(data["sound_speed"],data["radius"], dustRadius)))
        #print "tau at 3000: ",  GetPropertyAtRadius(data["tau"],data["radius"], 3000.0 | units.RSun)
        print(("density at 340: ",  GetPropertyAtRadius(data["density"],data["radius"], dustRadius)))
        print(("m over 340: ", (M - m)))
        print(("M total: ", M))
        print(("time: ", ((M-m)/mdot)))



def PlotDensity(sphGiant,core,binary,i, outputDir, vmin, vmax, plotDust=False, dustRadius=700 | units.RSun, width = 20.0 | units.AU, side_on = False, timeStep = 0.2):
    if not HAS_PYNBODY:
        print("problem plotting")
        return

    #width = 0.08 * sphGiant.position.lengths_squared().amax().sqrt()
    #width = 5.0 * sphGiant.position.lengths_squared().amax().sqrt()
    #width = 4.0 | units.AU
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    pyndata = convert_particles_to_pynbody_data(sphGiant, length_unit, pynbody_unit)
    UnitlessArgs.strip([1]|length_unit, [1]|length_unit)
    if not side_on:
        '''
        with angmom.faceon(pyndata, cen=[0.0,0.0,0.0], vcen=[0.0,0.0,0.0]):
            
            pynbody_sph.image(pyndata, resolution=2000,width=width.value_in(length_unit), units='g cm^-3',
                                 vmin= vmin, vmax= vmax, cmap="hot", title = str(i * timeStep) + " days")
            UnitlessArgs.current_plot = native_plot.gca()
            native_plot.xlim(xmax=2, xmin=-10)
            native_plot.ylim(ymax=6, ymin=-6)
            native_plot.xticks([-10,-8,-6,-4,-2,0,2],[-6,-4,-2,0,2,4,6])
            native_plot.ylabel('y[AU]')
            yLabel = 'y[AU]'
            #pyplot.xlim(-5,-2)
            if core.mass != 0 | units.MSun:
                if core.x >= -1* width / 2.0 and core.x <= width/ 2.0 and core.y >= -1 * width/ 2.0 and core.y <= width / 2.0:
                    #both coordinates are inside the boundaries- otherwise dont plot it
                    scatter(core.x, core.y, c="r")
            scatter(binary.x, binary.y, c="w")
            #pyplot.xlim(-930, -350)
            #pyplot.ylim(-190,390)
            if plotDust:
                circle_with_radius(core.x, core.y,dustRadius, fill=False, color='white', linestyle= 'dashed', linewidth=3.0)
        '''
        print("nothing")
    else:
        #outputDir += "/side_on"
        outputDir += "/both"
        pyplot.rc('font',family='Serif',size=57)
        fig, (face, side) = pyplot.subplots(nrows=1,ncols=2, figsize=(36,14))
        fig.subplots_adjust(wspace=0.1,hspace=0.0)
        with angmom.faceon(pyndata, cen=[0.0, 0.0, 0.0], vcen=[0.0, 0.0, 0.0]):
            pynbody_sph.image(pyndata, subplot=face, resolution=2000, width=width.value_in(length_unit),
                              units='g cm^-3',show_cbar=False, clear=False,
                              vmin=vmin, vmax=vmax, cmap="hot")
            face.set_adjustable('box-forced')
            if core.mass != 0 | units.MSun:
                if core.x >= -1* width / 2.0 and core.x <= width/ 2.0 and core.y >= -1 * width/ 2.0 and core.y <= width / 2.0:
                    #both coordinates are inside the boundaries- otherwise dont plot it
                    face.scatter(core.x.value_in(units.AU), core.y.value_in(units.AU), c="r")
            face.scatter(binary.x.value_in(units.AU), binary.y.value_in(units.AU), c="w")
            face.set_ylabel('y[AU]',fontsize=60, labelpad=-45)
            face.set_xlabel('x[AU]',fontsize=55)
        with angmom.sideon(pyndata, cen=[0.0, 0.0, 0.0], vcen=[0.0, 0.0, 0.0]):
            imside = pynbody_sph.image(pyndata, subplot=side, resolution=2000, width=width.value_in(length_unit),
                              units='g cm^-3', show_cbar=False, ret_im=True, clear=False,
                              vmin=vmin, vmax=vmax, cmap="hot")
            side.set_adjustable('box-forced')
            if core.mass != 0 | units.MSun:
                if core.x >= -1 * width / 2.0 and core.x <= width / 2.0 and core.z >= -1 * width / 2.0 and core.z <= width / 2.0:
                    # both coordinates are inside the boundaries- otherwise dont plot it
                    side.scatter(core.x.value_in(units.AU), core.z.value_in(units.AU), c="r")
            side.scatter(binary.x.value_in(units.AU), binary.z.value_in(units.AU), c="w")
            side.set_ylabel('z[AU]',fontsize=60,labelpad=-45)
            side.set_xlabel('x[AU]',fontsize=55)
        fig.suptitle(str(i * timeStep) + " days")
        cbar = pyplot.colorbar(imside, aspect=10,fraction=0.1,pad=0.01,panchor=(0,0),anchor=(0,0))
        cbar.set_label('Density $[g/cm^3]$',fontsize=60)
        #bar_ticks = cbar.ax.get_yticklabels()
        #bar.ax.set_yticklabels(cbar_ticks,fontsize=30)
        '''    
        with angmom.sideon(pyndata, cen=[0.0,0.0,0.0], vcen=[0.0,0.0,0.0]):
            pynbody_sph.sideon_image(pyndata, resolution=2000,width=width.value_in(length_unit), units='g cm^-3',
                                            vmin= vmin, vmax= vmax, cmap="hot", title = str(i * timeStep) + " days")
            UnitlessArgs.current_plot = native_plot.gca()
            native_plot.ylabel('z[AU]')
            yLabel = 'z[AU]'
            if core.mass != 0 | units.MSun:
                if core.x >= -1* width / 2.0 and core.x <= width/ 2.0 and core.z >= -1 * width/ 2.0 and core.z <= width / 2.0:
                    #both coordinates are inside the boundaries- otherwise dont plot it
                    scatter(core.x, core.z, c="r")
            scatter(binary.x, binary.z, c="w")
            if plotDust:
                circle_with_radius(core.x, core.z,dustRadius, fill=False, color='white', linestyle= 'dashed', linewidth=3.0)
        '''
    #native_plot.colorbar(fontsize=20.0)
    matplotlib.rcParams.update({'font.size': 60, 'font.family': 'Serif','xtick.labelsize': 60, 'ytick.labelsize': 60})
    pyplot.rcParams.update({'font.size': 60, 'font.family': 'Serif'})
    #pyplot.rc('text', usetex=True)
    #cbar.ax.set_yticklabels(cbar
    # .ax.get_yticklabels(), fontsize=24)
    #pyplot.axes.labelsize(24)
    pyplot.savefig(outputDir + "/plotting_{0}.jpg".format(i), transparent=False)
    pyplot.close()

def PlotVelocity(sphGiant,core,binary,step, outputDir, vmin, vmax, timeStep = 0.2):
    if not HAS_PYNBODY:
        print(HAS_PYNBODY)
        print("problem plotting")
        return
    width = 1.5 * sphGiant.position.lengths_squared().amax().sqrt()
    length_unit, pynbody_unit = _smart_length_units_for_pynbody_data(width)
    pyndata = convert_particles_to_pynbody_data(sphGiant, length_unit, pynbody_unit)
    UnitlessArgs.strip([1]|length_unit, [1]|length_unit)
    pynbody_sph.velocity_image(pyndata, width=width.value_in(length_unit), units='g cm^-3',vmin= vmin, vmax= vmax,
                               title = str(step * timeStep) + " days")
    UnitlessArgs.current_plot = native_plot.gca()
    #print core.mass
    #if core.mass != 0 |units.MSun:
    #    scatter(core.x, core.y, c="r")
    scatter(core.x, core.y, c="r")
    scatter(binary.x, binary.y, c="w")
    pyplot.savefig(outputDir + "/velocity/velocity_plotting_{0}.jpg".format(step), transparent=False)
    pyplot.close()

def Plot1Axe(x, fileName, outputDir, timeStep= 1400.0/7000.0, beginStep = 0, toPlot=False):
    if len(x) == 0:
        return
    beginTime = beginStep * timeStep
    timeLine = [beginTime + time * timeStep for time in range(len(x))] | units.day

    textFile = open(outputDir + '/' + fileName + 'time_' + str(beginTime) + "_to_" + str(beginTime + (len(x) - 1.0) * timeStep) + 'days.txt', 'w')
    textFile.write(', '.join([str(y) for y in x]))
    textFile.close()

    if toPlot:
        native_plot.figure(figsize= (20, 20), dpi= 80)
        plot(timeLine,x)
        xlabel('time[days]')
        native_plot.savefig(outputDir + '/' + fileName + 'time_' + str(beginTime) + "_to_" + str(beginTime + (len(x) - 1.0) * timeStep) + 'days.jpg')

def PlotAdaptiveQuantities(arrayOfValueAndNamePairs, outputDir, beginStep = 0, timeStep= 1400.0/7000.0, toPlot = False):
    for a in arrayOfValueAndNamePairs:
        if a[0]:
            Plot1Axe(a[0], a[1], outputDir, timeStep, beginStep, toPlot)

def PlotEccentricity(eccentricities, outputDir, beginStep = 0, timeStep= 1400.0/7000.0, toPlot = False):
    for e in eccentricities:
        if e[0] != []:
            Plot1Axe(e[0], e[1], outputDir, timeStep, beginStep, toPlot)

def PlotBinaryDistance(distances, outputDir, beginStep = 0, timeStep= 1400.0/7000.0, toPlot = False):
    for d in distances:
        if d[0]:
            Plot1Axe(d[0], d[1], outputDir, timeStep, beginStep, toPlot)

def PlotQuadropole(Qxx,Qxy,Qxz,Qyx, Qyy,Qyz,Qzx,Qzy,Qzz, outputDir = 0, timeStep = 1400.0/70000.0, beginStep = 0):
    if len(Qxx) == 0:
        return
    beginTime = beginStep * timeStep
    timeLine = [beginTime + time * timeStep for time in range(len(Qxx))] | units.day

    textFile = open(outputDir + '/quadropole_time_' + str(beginTime) + "_to_" + str(beginTime + (len(Qxx) - 1.0) * timeStep) + 'days.txt', 'w')

    textFile.write("Qxx,Qxy,Qxz,Qyx,Qyy,Qyz,Qzx,Qzy,Qzz\r\n")
    for i in range(0, len(Qxx)):
        textFile.write(' ,'.join([str(Qxx[i] * 10**40), str(Qxy[i] * 10**40), str(Qxz[i] * 10**40),
                                  str(Qyx[i] * 10**40), str(Qyy[i] * 10**40), str(Qyz[i] * 10**40),
                                  str(Qzx[i] * 10**40), str(Qzy[i] * 10**40), str(Qzz[i] * 10**40)]))
        textFile.write('\r\n')
    textFile.close()

def AnalyzeBinaryChunk(savingDir,gasFiles,dmFiles,outputDir,chunk, vmin, vmax, beginStep, binaryDistances,binaryDistancesUnits,
                       semmimajors,semmimajorsUnits, eccentricities, innerMass, innerMassUnits,
                       pGas, pGasUnits, pGiant, pGiantUnits, pCompCore, pCompCoreUnits, pTot, pTotUnits,
                    kGas, kGasUnits, uGiant, uGiantUnits, kCore, kCoreUnits,
                       kComp, kCompUnits, eTot, eTotUnits,
                       innerAngularMomenta,
                       innerAngularMomentaUnits, companionAngularMomenta, companionAngularMomentaUnits,
                       giantAngularMomenta, giantAngularMomentaUnits,
                       gasAngularMomenta, gasAngularMomentaUnits,
                        angularCores, angularCoresUnits,
                       totAngularMomenta, totAngularMomentaUnits,
                       massLoss, massLossUnits,
                       Qxx,Qxy,Qxz,Qyx,Qyy,Qyz,Qzx,Qzy,Qzz,
                       toPlot = False, plotDust=False, dustRadius= 340.0 | units.RSun, massLossMethod="estimated",
                       timeStep=0.2):

    for index,step in enumerate(chunk):
        i = beginStep + index
        print(("step #",i))

        for f in [obj for obj in gc.get_objects() if isinstance(obj, h5py.File)]:
            try:
                f.close()
            except:
                pass
        gas_particles_file = os.path.join(os.getcwd(), savingDir,gasFiles[step])
        dm_particles_file = None
        if len(dmFiles) > 0:
            dm_particles_file = os.path.join(os.getcwd(),savingDir, dmFiles[step])
        sphGiant = SphGiant(gas_particles_file, dm_particles_file, opposite=True)
        sphPointStar = Particle()
        sphPointStar.position = sphGiant.position
        sphPointStar.velocity = sphGiant.velocity
        sphPointStar.mass = sphGiant.mass
        sphPointStar.radius = sphGiant.radius
        try:
            binary = LoadBinaries(dm_particles_file)
            companion = binary[1]
        except: #no binary
            binary = []
            companion = sphPointStar
        #print binary
        if len(binary) > 1:
            isBinary= True
            binary = Star(companion, sphPointStar)
        else:
            isBinary=False
            #binary = Star(sphPointStar, sphPointStar)

        centerOfMassPosition = [0.0,0.0,0.0] | units.m
        centerOfMassVelocity = [0.0,0.0,0.0] | units.m/units.s

        
        #print [CalculateVectorSize(part.velocity).as_quantity_in(units.m / units.s) for part in sphGiant.gasParticles]
        if isBinary:
            if CalculateVectorSize(CalculateSeparation(sphGiant.core, companion)) < min(sphGiant.core.radius,
                                                                                        companion.radius):
                print(("merger between companion and the giant! step: ", step))
                # break

            parts = Particles()
            parts.add_particle(sphGiant.core)
            parts.add_particles(sphGiant.gasParticles)
            parts.add_particle(companion)

            print(("com: ", parts.center_of_mass(), step))
            print(("com v: ", parts.center_of_mass_velocity(), i))
            
            centerOfMassPosition = parts.center_of_mass()
            centerOfMassVelocity = parts.center_of_mass_velocity()
            
            comParticle = Particle()
            comParticle.position = centerOfMassPosition
            comParticle.velocity = centerOfMassVelocity
            
            '''    
            sphGiant.CountLeavingParticlesInsideRadius(com_position=centerOfMassPosition,
                                                       com_velocity=centerOfMassVelocity, companion=companion,
                                                       method=massLossMethod)
            print("leaving particles: ", sphGiant.leavingParticles)
            print("unbounded mass: ", sphGiant.totalUnboundedMass)
            massLoss[i] = sphGiant.totalUnboundedMass.value_in(massLossUnits)
            
            semmimajor = CalculateSemiMajor(CalculateVelocityDifference(companion, sphGiant.core), CalculateSeparation(companion, sphGiant.core),companion.mass + sphGiant.core.mass).as_quantity_in(units.AU)
            CalculateEccentricity(companion, sphGiant.core)
            #check if the companion is inside, take into account only the inner mass of the companion's orbit
            sphGiant.CalculateInnerSPH(companion, com_position=centerOfMassPosition, com_velocity=centerOfMassVelocity)
            #print "innerGasMass: ", sphGiant.innerGas.mass.value_in(units.MSun)
            innerMass[i] = sphGiant.innerGas.mass.value_in(innerMassUnits)
            
            newBinaryVelocityDifference = CalculateVelocityDifference(companion, sphGiant.innerGas)
            newBinarySeparation = CalculateSeparation(companion, sphGiant.innerGas)
            newBinaryMass = companion.mass + sphGiant.innerGas.mass
            newBinarySpecificEnergy = CalculateSpecificEnergy(newBinaryVelocityDifference,newBinarySeparation,sphGiant.innerGas,companion)
            semmimajor = CalculateSemiMajor(newBinaryVelocityDifference, newBinarySeparation, newBinaryMass).as_quantity_in(units.AU)
            eccentricity = CalculateEccentricity(companion, sphGiant.innerGas)
            eccentricities[i] = eccentricity
            binaryDistances[i] = CalculateVectorSize(newBinarySeparation).value_in(binaryDistancesUnits)
                        
            
            sphGiant.CalculateEnergies(comV=centerOfMassVelocity)

            uGiant[i] = sphGiant.thermalEnergy.value_in(uGiantUnits)
            kGas[i] = sphGiant.gasKinetic.value_in(kGasUnits)
            kCore[i] = sphGiant.coreKinetic.value_in(kCoreUnits)
            kComp[i] = (0.5 * companion.mass * (CalculateVectorSize(companion.velocity))**2).value_in(kCompUnits)

            # total energies
            kTot = (sphGiant.kineticEnergy).value_in(kGasUnits) + kComp[i]


            pGas[i] = sphGiant.gasPotential.value_in(pGasUnits)
            pGiant[i] = sphGiant.potentialEnergy.value_in(pGiantUnits)
            print(sphGiant.potentialEnergy)
            pCompCore[i] = CalculatePotentialEnergy(sphGiant.core, companion).value_in(pCompCoreUnits)
            
            pCompGas = (sphGiant.potentialEnergyWithParticle(companion)).value_in(pGasUnits)

            pTot[i] = pGiant[i] + pCompGas + pCompCore[i]
            eTot[i] = kTot + pTot[i] + uGiant[i]
                     
            
            try:
                separation = CalculateSeparation(companion, comParticle)
                specificAngularCOM = CalculateSpecificMomentum(CalculateVelocityDifference(companion, comParticle),
                                                                separation)

                angularOuterCOMx = companion.mass * specificAngularCOM[0]
                angularOuterCOMy = companion.mass * specificAngularCOM[1]
                angularOuterCOMz = companion.mass * specificAngularCOM[2]
                companionAngularMomenta[i] = angularOuterCOMz.value_in(companionAngularMomentaUnits)
                companionAngularMomentaTot = ((angularOuterCOMx ** 2 + angularOuterCOMy ** 2 +
                                               angularOuterCOMz ** 2) ** 0.5).value_in(
                    companionAngularMomentaUnits)



                gasAngularMomentaTot = sphGiant.GetAngularMomentumOfGas()#centerOfMassPosition, centerOfMassVelocity)
                gasAngularMomenta[i] = gasAngularMomentaTot[2].value_in(gasAngularMomentaUnits)

                print companionAngularMomenta[i], companionAngularMomentaTot, gasAngularMomenta[i], gasAngularMomentaTot[0]
                
                angularGiant = sphGiant.GetAngularMomentum(centerOfMassPosition, centerOfMassVelocity)
                giantAngularMomenta[i] = angularGiant[2].value_in(giantAngularMomentaUnits)

                angularCore = CalculateSpecificMomentum(CalculateVelocityDifference(sphGiant.core, comParticle),
                                                                CalculateSeparation(sphGiant.core, comParticle))
                angularCoresx = sphGiant.core.mass * angularCore[0] + angularOuterCOMx
                angularCoresy = sphGiant.core.mass * angularCore[1] + angularOuterCOMy
                angularCoresz = sphGiant.core.mass * angularCore[2] + angularOuterCOMz

                angularCores[i] = angularCoresz.value_in(angularCoresUnits)
                    #((angularCoresx ** 2 + angularCoresy ** 2 + angularCoresz ** 2) ** 0.5).value_in(angularCoresUnits)

                angularTotx = angularGiant[0] + angularOuterCOMx
                angularToty = angularGiant[1] + angularOuterCOMy
                angularTotz = angularGiant[2] + angularOuterCOMz
                totAngularMomenta[i] = angularTotz.value_in(totAngularMomentaUnits)
                #((angularTotx ** 2 + angularToty ** 2 + angularTotz ** 2) ** 0.5).value_in(totAngularMomentaUnits)

            except:
                print("could not calculate angular momenta, ", sys.exc_info()[0])
                        
            semmimajors[i] = semmimajor.value_in(semmimajorsUnits)
            
            #check if the binary is breaking up
            if newBinarySpecificEnergy > 0 | (units.m **2 / units.s **2):
                print("binary is breaking up", binary.specificEnergy, step)

            Qxx_g,Qxy_g,Qxz_g,Qyx_g,Qyy_g,Qyz_g,Qzx_g,Qzy_g,Qzz_g = sphGiant.CalculateQuadropoleMoment()
            Qxx_p,Qxy_p,Qxz_p,Qyx_p,Qyy_p,Qyz_p,Qzx_p,Qzy_p,Qzz_p = CalculateQuadropoleMomentOfParticle(companion) # add the companion to the calculation
            print(Qxx_p, Qxx[i]+Qxx_p+Qxx_g)
            Qxx[i] = (Qxx[i]+Qxx_p+Qxx_g)/(10**40)
            print(
                Qxx[i])
            Qxy[i] += (Qxy_p + Qxy_g)/(10**40)
            Qxz[i] += (Qxz_p + Qxz_g)/(10**40)
            Qyx[i] += (Qyx_p + Qyx_g)/(10**40)
            Qyy[i] += (Qyy_p + Qyy_g)/(10**40)
            Qyz[i] += (Qyz_p + Qyz_g)/(10**40)
            Qzx[i] += (Qzx_p + Qzx_g)/(10**40)
            Qzy[i] += (Qzy_p + Qzy_g)/(10**40)
            Qzz[i] += (Qzz_p + Qzz_g)/(10**40)
            '''


        
        central_position = centerOfMassPosition#sphGiant.gas.position #centerOfMassPosition
        central_velocity = centerOfMassVelocity#sphGiant.gas.velocity #centerOfMassVelocity

        
        sphGiant.gasParticles.position -= central_position
        sphGiant.gasParticles.velocity -= central_velocity
        sphGiant.core.position -= central_position
        sphGiant.core.velocity -= central_velocity

        companion.position -= central_position
        companion.velocity -= central_velocity
        
        print((central_position.as_quantity_in(units.AU), sphGiant.gasParticles.center_of_mass().as_quantity_in(units.AU),sphGiant.core.position.as_quantity_in(units.AU)))
        
        temperature_density_plot(sphGiant, step, outputDir, toPlot)
        #innerAngularMomenta[i] = sphGiant.innerGas.angularMomentum[2].value_in(innerAngularMomentaUnits)
        if toPlot:
            PlotDensity(sphGiant.gasParticles,sphGiant.core,companion, step , outputDir, vmin, vmax, plotDust= plotDust,
                        dustRadius=dustRadius, timeStep=timeStep)
            PlotDensity(sphGiant.gasParticles,sphGiant.core,companion, step, outputDir, vmin, vmax, plotDust= plotDust,
                        dustRadius=dustRadius, side_on=True, timeStep=timeStep)
            PlotVelocity(sphGiant.gasParticles,sphGiant.core,companion, step, outputDir, vmin, vmax, timeStep=timeStep)

    for f in [obj for obj in gc.get_objects() if isinstance(obj,h5py.File)]:
        try:
            f.close()
        except:
            pass

def AnalyzeTripleChunk(savingDir, gasFiles, dmFiles, outputDir, chunk, vmin, vmax, beginStep,
                       binaryDistances, tripleDistances, triple1Distances, triple2Distances,
                       aInners, aOuters, aOuters1, aOuters2,
                       eInners, eOuters, eOuters1, eOuters2, inclinations, innerMass, innerMass1, innerMass2, localDensity,
                       kInner, kOuter, kOuter1, kOuter2, pInner, pOuter, pOuter1, pOuter2,
                       kGas, uGas, pGas, kCore, pOuterCore, pCores, pPartGas, force, omegaInner, omegaGiant, omegaTot,
                       kTot, pTot, eTot,
                       angularInner, angularOuter,angularOuter1,angularOuter2, angularOuterCOM1, angularOuterCOM2, angularOuterCOM,
                       angularGasCOM, angularTot, localRadius=50.0|units.RSun,
                       toPlot = False, opposite= False, axesOriginInInnerBinaryCenterOfMass= False, timeStep=0.2):
    energyUnits = units.kg*(units.km**2) / units.s**2
    specificAngularMomentumUnits = (energyUnits * units.s / units.kg) * 10000

    for i in [j - beginStep for j in chunk]:
        print((time.ctime(), "step: ", i))
        gas_particles_file = os.path.join(os.getcwd(), savingDir,gasFiles[i + beginStep])
        dm_particles_file = os.path.join(os.getcwd(),savingDir, dmFiles[i + beginStep])

        sphGiant = SphGiant(gas_particles_file, dm_particles_file, opposite= opposite)
        print((sphGiant.core))
        if i == 1:
            print((sphGiant.gasParticles[0]))
        #print "neigbbours:", sphGiant.FindLowestNumberOfNeighbours()
        #print "smallest cell radius: ", sphGiant.FindSmallestCell()
        #binary = Particles(2,pickle.load(open(os.path.join(os.getcwd(),savingDir,"binary.p"),"rb")))
        binary = LoadBinaries(dm_particles_file, opposite= opposite)

        particle1 , particle2 = binary[0] , binary[1]
        innerBinary = Star(particle1,particle2)
        
        #change the position and velocity of center of mass to 0
        centerOfMassPosition = (sphGiant.position * sphGiant.mass + innerBinary.position * innerBinary.mass) / (sphGiant.mass + innerBinary.mass)
        centerOfMassVelocity = (sphGiant.v * sphGiant.mass + innerBinary.velocity * innerBinary.mass) / (sphGiant.mass + innerBinary.mass)
        print(("center of mass position: ", centerOfMassPosition))
        print(("center of mass velocity: ", centerOfMassVelocity))

        comParticle = Particle()
        comParticle.position = centerOfMassPosition
        comParticle.velocity = centerOfMassVelocity

        triple1 = Star(particle1, sphGiant)
        triple2 = Star(particle2, sphGiant)

        aInner = CalculateSemiMajor(innerBinary.velocityDifference,innerBinary.separation, innerBinary.mass)
        eInner = CalculateEccentricity(particle1,particle2)

        if CalculateVectorSize(innerBinary.separation) <= particle1.radius+ particle2.radius:
            print(("merger between the inner binary!" , innerBinary.separation.as_quantity_in(units.RSun) , i * timeStep))

        if CalculateVectorSize(CalculateSeparation(sphGiant.core,particle1)) <= sphGiant.core.radius + particle1.radius:
            print(("merger between particle1 and the giant!" , i * timeStep))
            #break

        if CalculateVectorSize(CalculateSeparation(sphGiant.core, particle2)) <= sphGiant.core.radius+ particle2.radius:
            print(("merger between particle 2 and the giant!" , i * timeStep))
            #break
        #check if the binry is breaking up
        if innerBinary.specificEnergy > 0 | (units.m **2 / units.s **2):
            print(("binary is breaking up", innerBinary.specificEnergy , i * timeStep))

        #check if the couple particle1 + giant are breaking up
            if triple1.specificEnergy > 0 | (units.m **2 / units.s **2):
                print(("triple1 is breaking up", triple1.specificEnergy , i * timeStep))

                #check if the couple particle2 + giant are also breaking up
                if triple2.specificEnergy > 0 | (units.m **2 / units.s **2):
                    print(("triple2 is also breaking up", triple2.specificEnergy , i * timeStep))
                    #break

            #check if the couple particle2 + giant are breaking up
            if triple2.specificEnergy > 0 | (units.m **2 / units.s **2):
                print(("triple2 is breaking up", triple2.specificEnergy, i * timeStep))

            separationStep = 0
        '''
        #all the three are connected
        sphGiant.CountLeavingParticlesInsideRadius()
        print("leaving particles: ", sphGiant.leavingParticles)
        print("unbounded mass: ", sphGiant.totalUnboundedMass)
        print(time.ctime(), "beginning innerGas calculations of step ", i)
        
        sphGiant.CalculateInnerSPH(innerBinary, localRadius)
        innerMass[i] = sphGiant.innerGas.mass.value_in(units.MSun)

        tripleMass = innerBinary.mass + sphGiant.innerGas.mass
        tripleVelocityDifference = CalculateVelocityDifference(innerBinary,sphGiant.innerGas)
        tripleSeparation = CalculateSeparation(innerBinary,sphGiant.innerGas)

        aOuter = CalculateSemiMajor(tripleVelocityDifference, tripleSeparation, tripleMass)
        eOuter = CalculateEccentricity(innerBinary,sphGiant.innerGas)

        inclination = CalculateInclination(tripleVelocityDifference, tripleSeparation, innerBinary.velocityDifference, innerBinary.separation)

        binaryDistances[i] = CalculateVectorSize(innerBinary.separation).value_in(units.RSun)
        tripleDistances[i] = CalculateVectorSize(tripleSeparation).value_in(units.RSun)
        aInners[i] = aInner.value_in(units.AU)
        aOuters[i] = aOuter.value_in(units.AU)
        eInners[i] = eInner
        eOuters[i] = eOuter
        localDensity[i] = sphGiant.localDensity.value_in(units.MSun/units.RSun**3)
        inclinations[i] = inclination
        
        
        kInner[i]= innerBinary.kineticEnergy.value_in(energyUnits)
        pInner[i] = innerBinary.potentialEnergy.value_in(energyUnits)
        angularInner[i] = CalculateVectorSize(innerBinary.angularMomentum).value_in(specificAngularMomentumUnits * units.kg)
        omegaInner[i] = innerBinary.omega.value_in(energyUnits)
        giantForce = sphGiant.gravityWithParticle(particle1) + sphGiant.gravityWithParticle(particle2)
        force[i] = CalculateVectorSize(giantForce).value_in(energyUnits/units.km)
        #inner gas of the com of the inner binary
        kOuter[i] = kInner[i] + sphGiant.innerGas.kineticEnergy.value_in(energyUnits)
        pOuter[i] = -(constants.G*sphGiant.innerGas.mass*innerBinary.mass/
                      (tripleDistances[i] | units.RSun)).value_in(energyUnits)
        angularOuter[i] = (innerBinary.mass * sphGiant.innerGas.mass *
                           (constants.G*aOuter/(innerBinary.mass+sphGiant.innerGas.mass))**0.5)\
                                .value_in(specificAngularMomentumUnits * units.kg)
        print angularOuter[i]
        #inner gas of particle 1
        innerMass1[i] , aOuters1[i], eOuters1[i], triple1Distances[i] = CalculateBinaryParameters(particle1, sphGiant)
        kOuter1[i] = (sphGiant.innerGas.kineticEnergy +
                      0.5*particle1.mass*(particle1.vx**2+particle1.vy**2+particle1.vz**2)).value_in(energyUnits)
        pOuter1[i] = -(constants.G*sphGiant.innerGas.mass*particle1.mass/
                       (triple1Distances[i] | units.RSun)).value_in(energyUnits)
        angularOuter1[i] = (particle1.mass*sphGiant.innerGas.mass*
                               (constants.G*(aOuters1[i] | units.AU)/(particle1.mass+sphGiant.innerGas.mass))**0.5).value_in(specificAngularMomentumUnits* units.kg)
        
        #inner gas of particle2
        innerMass2[i] , aOuters2[i], eOuters2[i], triple2Distances[i] = CalculateBinaryParameters(particle2, sphGiant)
        kOuter2[i] = (sphGiant.innerGas.kineticEnergy +
                      0.5*particle1.mass*(particle2.vx**2+particle2.vy**2+particle2.vz**2)).value_in(energyUnits)
        pOuter2[i] = (-constants.G*sphGiant.innerGas.mass*particle2.mass/
                      (triple2Distances[i] | units.RSun)).value_in(energyUnits)
        angularOuter2[i] = (particle2.mass*sphGiant.innerGas.mass*
                           (constants.G*(aOuters2[i] | units.AU)/(particle2.mass+sphGiant.innerGas.mass))**0.5).value_in(specificAngularMomentumUnits * units.kg)
        
        #real energies
        sphGiant.CalculateEnergies()
        kGas[i] = sphGiant.gasKinetic.value_in(energyUnits)
        uGas[i] = sphGiant.thermalEnergy.value_in(energyUnits)
        pGas[i] = sphGiant.gasPotential.value_in(energyUnits)
        kCore[i] = sphGiant.coreKinetic.value_in(energyUnits)
        pOuterCore[i] = (CalculatePotentialEnergy(sphGiant.core,innerBinary)).value_in(energyUnits)
        pPartsCore = CalculatePotentialEnergy(sphGiant.core, particle1) + \
                     CalculatePotentialEnergy(sphGiant.core, particle2)
        pCores[i] = pPartsCore.value_in(energyUnits)
        pPartGas[i] = (sphGiant.potentialEnergyWithParticle(particle1, 0.0 | units.m) +
                   sphGiant.potentialEnergyWithParticle(particle2, 0.0 | units.m)).value_in(energyUnits)
        #total energies
        kTot[i] = (sphGiant.kineticEnergy).value_in(energyUnits) + kInner[i]
        pTot[i] = sphGiant.potentialEnergy.value_in(energyUnits) + pInner[i] + pPartGas[i] + pCores[i]
        eTot[i] = kTot[i] + pTot[i] + uGas[i]
        print("pTot: ", pTot[i], pGas[i],pOuterCore[i],pInner[i])
        print("kTot: ",kTot[i])
        print("eTot: ", eTot[i])
        
        try:
            separation1 = CalculateSeparation(particle1,comParticle)
            specificAngularCOM1 = CalculateSpecificMomentum(CalculateVelocityDifference(particle1,comParticle), separation1)
            angularOuterCOM1[i] = particle1.mass.value_in(units.kg)*CalculateVectorSize([specificAngularCOM1[0].value_in(specificAngularMomentumUnits),
                                                                      specificAngularCOM1[1].value_in(specificAngularMomentumUnits),
                                                                      specificAngularCOM1[2].value_in(specificAngularMomentumUnits)])
            separation2 = CalculateSeparation(particle2, comParticle)
            specificAngularCOM2 =  CalculateSpecificMomentum(CalculateVelocityDifference(particle2, comParticle),separation2)
            angularOuterCOM2[i] = particle2.mass.value_in(units.kg) * CalculateVectorSize([specificAngularCOM2[0].value_in(specificAngularMomentumUnits)
                                                                                              ,specificAngularCOM2[1].value_in(specificAngularMomentumUnits)
                                                                                              ,specificAngularCOM2[2].value_in(specificAngularMomentumUnits)
                                                                                           ])
            angularOuterCOMx = particle1.mass * specificAngularCOM1[0] + particle2.mass * specificAngularCOM2[0]
            angularOuterCOMy = particle1.mass * specificAngularCOM1[1] + particle2.mass * specificAngularCOM2[1]
            angularOuterCOMz = particle1.mass * specificAngularCOM1[2] + particle2.mass * specificAngularCOM2[2]
            angularOuterCOM[i] = ((angularOuterCOMx**2+angularOuterCOMy**2+angularOuterCOMz**2)**0.5).value_in(specificAngularMomentumUnits * units.kg)

            angularGasCOM[i] = CalculateVectorSize(sphGiant.GetAngularMomentumOfGas(centerOfMassPosition, centerOfMassVelocity)).value_in(specificAngularMomentumUnits * units.kg)
            angularGiant = sphGiant.GetAngularMomentum(centerOfMassPosition,centerOfMassVelocity)
            angularTotx = angularGiant[0] + angularOuterCOMx
            angularToty = angularGiant[1] + angularOuterCOMy
            angularTotz = angularGiant[2] + angularOuterCOMz
            angularTot[i] = ((angularTotx**2 + angularToty**2 + angularTotz**2)**0.5).value_in(specificAngularMomentumUnits * units.kg)
            print "angular: ", angularTotx, angularToty, angularTotz
            omegaGiant[i] = sphGiant.omegaPotential.value_in(energyUnits)
            comp = Particles(particles=[particle1,particle2])
            comp.move_to_center()
            comp.position -= comParticle.position
            comp.velocity -=comParticle.velocity
            omegaTot[i] = omegaInner[i] + omegaGiant[i] + CalculateOmega(comp).value_in(energyUnits)
            print("omega tot: ", omegaTot[i])
        except:
            print("could not calculate angular momenta, ", sys.exc_info()[0])
            #raise
        '''


        if toPlot:
            central_position = centerOfMassPosition #sphGiant.gas.position
            central_velocity = centerOfMassVelocity #sphGiant.gas.velocity
            '''
            if axesOriginInInnerBinaryCenterOfMass:
                central_position = innerBinary.position
                central_velocity = innerBinary.velocity
            '''
            print((time.ctime(), "temperature_density_plotting of step ", i))
            temperature_density_plot(sphGiant, i + beginStep , outputDir, toPlot)
            print((time.ctime(), "finished temperature plotting of step: ", i))
            sphGiant.gasParticles.position -= central_position
            sphGiant.gasParticles.velocity -= central_velocity
            sphGiant.core.position -= central_position
            sphGiant.core.velocity -= central_velocity
            binary[0].position -= central_position
            binary[0].velocity -= central_velocity
            binary[1].position -= central_position
            binary[1].velocity -= central_velocity
            if axesOriginInInnerBinaryCenterOfMass:
                PlotDensity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin=5e29, vmax= 1e35, width= 30.0 * 3.0 | units.RSun, timeStep=timeStep)
                PlotDensity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin=5e29, vmax= 1e35, width= 30.0 * 3.0 | units.RSun, side_on=True, timeStep=timeStep)
            else:
                PlotDensity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin, vmax, width= 6.0 | units.AU, timeStep=timeStep)
                PlotDensity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin, vmax, width= 6.0 | units.AU, side_on=True, timeStep=timeStep)
            PlotVelocity(sphGiant.gasParticles,sphGiant.core,binary,i + beginStep, outputDir, vmin, vmax)

        #close opened handles
        for f in [obj for obj in gc.get_objects() if isinstance(obj,h5py.File)]:
            try:
                f.close()
            except:
                pass

def AnalyzeBinary(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, toPlot = False,cpus=10,
                  skip=1,plotDust=False, dustRadius=700.0|units.RSun, massLossMethod="estimated", timeStep=0.2):
    if lastStep == 0 : # no boundary on last step
        lastStep = len(gasFiles)
    else:
        lastStep=min(lastStep, len(dmFiles))
    print(lastStep)
    workingRange = list(range(beginStep, lastStep,skip))
    energyUnits = units.kg*(units.km**2)/(units.s**2)
    angularMomentaUnits = energyUnits * units.s * 10000

    binaryDistances = MultiProcessArrayWithUnits(len(workingRange),units.RSun)
    semmimajors = MultiProcessArrayWithUnits(len(workingRange),units.AU)
    eccentricities = MultiProcessArrayWithUnits(len(workingRange),None)
    innerMass = MultiProcessArrayWithUnits(len(workingRange),units.MSun)
    pGas = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    pGiant = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    pCompCore = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    pTot = MultiProcessArrayWithUnits(len(workingRange),energyUnits)

    kGas = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    uGiant = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    kCore = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    kComp = MultiProcessArrayWithUnits(len(workingRange),energyUnits)
    eTot = MultiProcessArrayWithUnits(len(workingRange),energyUnits)

    innerAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    companionAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    giantAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    gasAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    coresAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    totAngularMomenta = MultiProcessArrayWithUnits(len(workingRange),angularMomentaUnits)
    massLoss = MultiProcessArrayWithUnits(len(workingRange), units.MSun)
    Qxx = multiprocessing.Array(c_float, [0.0 for i in workingRange])
    Qxy = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qxz = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qyx = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qyy = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qyz = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qzx = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qzy = multiprocessing.Array('f', [0.0 for i in workingRange])
    Qzz = multiprocessing.Array('f', [0.0 for i in workingRange])

    #chunkSize = (lastStep - beginStep) / 8
    chunkSize = int(math.floor(len(workingRange) / cpus))

    if chunkSize == 0:
        if lastStep - beginStep == 0:
            return
        else:
            chunkSize = 1
    leftovers = len(workingRange) - cpus * chunkSize
    chunks = []
    chunks += [workingRange[i:i+min(chunkSize+1,len(workingRange)-i)] for i in
               range(0,leftovers*(chunkSize+1),chunkSize+1)]
    chunks += [workingRange[i:i+min(chunkSize,len(workingRange)-i)] for i in
               range(leftovers*(chunkSize+1),len(workingRange),chunkSize)]

    processes = []
    print(chunks)
    i=0
    for chunk in chunks:
        processes.append(multiprocessing.Process(target= AnalyzeBinaryChunk,args=(savingDir,gasFiles,dmFiles,outputDir,
                                                                                  chunk, vmin, vmax, i,
                                                                                  binaryDistances.array, binaryDistances.units,
                                                                                  semmimajors.array, semmimajors.units,
                                                                                  eccentricities.array,
                                                                                  innerMass.array, innerMass.units,
                                                                                  pGas.array, pGas.units,
                                                                                  pGiant.array, pGiant.units,
                                                                                  pCompCore.array, pCompCore.units,
                                                                                  pTot.array, pTot.units,
                                                                                  kGas.array, kGas.units,
                                                                                  uGiant.array, uGiant.units,
                                                                                  kCore.array, kCore.units,
                                                                                  kComp.array, kComp.units,
                                                                                  eTot.array, eTot.units,
                                                                                  innerAngularMomenta.array, innerAngularMomenta.units,
                                                                                  companionAngularMomenta.array, companionAngularMomenta.units,
                                                                                  giantAngularMomenta.array, giantAngularMomenta.units,
                                                                                  gasAngularMomenta.array, gasAngularMomenta.units,
                                                                                  coresAngularMomenta.array, coresAngularMomenta.units,
                                                                                  totAngularMomenta.array, totAngularMomenta.units,
                                                                                  massLoss.array,massLoss.units,
                                                                                  Qxx,Qxy,Qxz,Qyx,Qyy,Qyz,Qzx,Qzy,Qzz,
                                                                                  toPlot,
                                                                                  plotDust,dustRadius, massLossMethod,
                                                                                  timeStep,)))
        i += len(chunk)
        #pool.map()
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    binaryDistances.plot("InnerBinaryDistances", outputDir + "/graphs",timeStep*skip, 1.0*beginStep/skip,False)
    semmimajors.plot("aInners", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    innerMass.plot("InnerMass", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    eccentricities.plot("eInners", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    innerAngularMomenta.plot("innerAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    companionAngularMomenta.plot("companionAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    giantAngularMomenta.plot("giantAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    gasAngularMomenta.plot("gasAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    coresAngularMomenta.plot("coresAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    totAngularMomenta.plot("totAngularMomenta", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    pGas.plot("pGas", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    pGiant.plot("pGiant", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    pCompCore.plot("pCompCore", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    pTot.plot("pTot", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    kGas.plot("kGas", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    uGiant.plot("uGiant", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    kCore.plot("kCore", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    kComp.plot("kComp", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    eTot.plot("eTot", outputDir + "/graphs",timeStep*skip,1.0*beginStep/skip,False)
    massLoss.plot("mass loss", outputDir + "/graphs", timeStep*skip,1.0*beginStep/skip,False)

    #PlotQuadropole(Qxx,Qxy,Qxz,Qyx,Qyy,Qyz,Qzx,Qzy,Qzz,outputDir+"/graphs",timeStep*skip,1.0*beginStep/skip)


def AnalyzeTriple(beginStep, lastStep, dmFiles, gasFiles, savingDir, outputDir, vmin, vmax, localRadius=50.0 | units.RSun
                  ,toPlot = False, opposite= False,  axesOriginInInnerBinaryCenterOfMass= False, timeStep=0.2):
    separationStep = multiprocessing.Value('i')
    if lastStep == 0 : # no boundary on last step
        lastStep = len(dmFiles)
    else:
        lastStep=min(lastStep, len(dmFiles))
    print(lastStep)

    binaryDistances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    tripleDistances = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
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
    inclinations = multiprocessing.Array('f', list(range(beginStep, lastStep)))
    innerMass = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    innerMass1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    innerMass2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    localDensity = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])

    kInner = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kOuter = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kOuter1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kOuter2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pInner = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pOuter = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pOuter1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pOuter2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kGas = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    uGas = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pGas = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kCore = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pOuterCore = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pCores = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pPartGas = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    force = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    omegaInner = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    omegaGiant = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    omegaTot = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    kTot = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    pTot = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    eTot = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])


    angularInner = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuter = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuter1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuter2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuterCOM1 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuterCOM2 = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularOuterCOM = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularGasCOM = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])
    angularTot = multiprocessing.Array('f', [-1.0 for i in range(beginStep, lastStep)])

    #angularInner, angularOuter,angularOuter1,angularOuter2 angularOuterCOM1, angularOuterCOM2, angularOuterCOM, angularGasCOM, angularTot
    #kInner, kOuter, kOuter1, kOuter2, pInner, pOuter, pOuter1, pOuter2, uInner, uOuter, uOuter1, uOuter2, kGas, uGas, pGas,
    # kCore, pOuterCore, pCores, pPartGas, force, omegaInner, omegaGiant, omegaTot, kTot, pTot, uTot, eTot


    cpus = multiprocessing.cpu_count() - 6
    chunkSize= (lastStep-beginStep)/(multiprocessing.cpu_count() - 6)
    print(("using ", multiprocessing.cpu_count() - 6, " cpus"))
    if chunkSize == 0:
        if lastStep - beginStep == 0:
            return
        else:
            chunkSize = 1

    chunks = [range(i,i+chunkSize) for i in range(beginStep,lastStep,chunkSize)]
    
    if len(chunks) > 1:
        lastChunkBegin = chunks[-2][-1]
    else:
        lastChunkBegin = beginStep
    chunks[-1] = range(lastChunkBegin, lastStep)
    processes = []
    print(chunks)
    for chunk in chunks:
        processes.append(multiprocessing.Process(target= AnalyzeTripleChunk,args=(savingDir, gasFiles, dmFiles, outputDir, chunk, vmin, vmax, beginStep,
                       binaryDistances, tripleDistances, triple1Distances, triple2Distances,
                       aInners, aOuters, aOuters1, aOuters2,
                       eInners, eOuters, eOuters1, eOuters2, inclinations, innerMass, innerMass1, innerMass2,localDensity,
                                                                                  kInner, kOuter, kOuter1, kOuter2,
                                                                                  pInner, pOuter, pOuter1, pOuter2,
                                                                                  kGas, uGas, pGas, kCore, pOuterCore,
                                                                                  pCores, pPartGas, force,
                                                                                  omegaInner, omegaGiant, omegaTot,
                                                                                  kTot, pTot,  eTot,
                                                                                  angularInner, angularOuter,
                                                                                  angularOuter1, angularOuter2,
                                                                                  angularOuterCOM1, angularOuterCOM2,
                                                                                  angularOuterCOM, angularGasCOM, angularTot,
                                                                                  localRadius, toPlot, opposite,
                                                                                  axesOriginInInnerBinaryCenterOfMass,
                                                                                  timeStep,)))
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    newBinaryDistances = AdaptingVectorQuantity()
    newTripleDistances = AdaptingVectorQuantity()
    newTriple1Distances = AdaptingVectorQuantity()
    newTriple2Distances = AdaptingVectorQuantity()
    newAInners = AdaptingVectorQuantity()
    newAOuters = AdaptingVectorQuantity()
    newAOuters1 = AdaptingVectorQuantity()
    newAOuters2 = AdaptingVectorQuantity()
    newInnerMass = AdaptingVectorQuantity()
    newInnerMass1 = AdaptingVectorQuantity()
    newInnerMass2 = AdaptingVectorQuantity()
    newLocalDensity = AdaptingVectorQuantity()
    for j in range(len(binaryDistances)-1):
        newBinaryDistances.append(float(binaryDistances[j]) | units.RSun)
        newTripleDistances.append(float(tripleDistances[j]) | units.RSun)
        newTriple1Distances.append(float(triple1Distances[j]) | units.RSun)
        newTriple2Distances.append(float(triple2Distances[j]) | units.RSun)
        newAInners.append(float(aInners[j]) | units.AU)
        newAOuters.append(float(aOuters[j]) | units.AU)
        newAOuters1.append(float(aOuters1[j]) | units.AU)
        newAOuters2.append(float(aOuters2[j]) | units.AU)
        newInnerMass.append(float(innerMass[j]) | units.MSun)
        newInnerMass1.append(float(innerMass1[j]) | units.MSun)
        newInnerMass2.append(float(innerMass2[j]) | units.MSun)
        newLocalDensity.append(float(localDensity[j]) | units.MSun / units.RSun**3)
    separationStep = int(separationStep.value)
    

    PlotBinaryDistance([(newBinaryDistances, "InnerBinaryDistances"), (newTripleDistances, "tripleDistances"), (newTriple1Distances, "triple1Distances"),
                        (newTriple2Distances, "triple2Distances")], outputDir + "/graphs", beginStep,timeStep,toPlot)
    PlotAdaptiveQuantities([(newAInners,"aInners"),(newAOuters, "aOuters")], outputDir+"/graphs",beginStep,timeStep,toPlot)
    PlotAdaptiveQuantities([(newAOuters1, "aOuters1"), (newAOuters2, "aOuters2")], outputDir+ "/graphs", separationStep,timeStep,toPlot)
    PlotEccentricity([(eInners, "eInners"), (eOuters, "eOuters")], outputDir + "/graphs", beginStep, timeStep, toPlot)
    PlotEccentricity([(eOuters1, "eOuters1"), (eOuters2, "eOuters2")],outputDir + "/graphs", separationStep,timeStep,toPlot)
    Plot1Axe(inclinations,"inclinations", outputDir+"/graphs", beginStep=beginStep, toPlot=toPlot)
    PlotAdaptiveQuantities([(innerMass, "InnerMass"), (innerMass1, "InnerMass1"), (innerMass2, "InnerMass2"),
                            (localDensity, "LocalDensity"),(kInner,"kInner"), (kOuter,"kOuter"), (kOuter1,"kOuter1"),
                            (kOuter2,"kOuter2"),(pInner,"pInner"), (pOuter,"pOuter"), (pOuter1,"pOuter1"),
                            (pOuter2,"pOuter2"),(kGas,"kGas"), (uGas,"uGas"), (pGas,"pGas"), (kCore,"kCore"),
                            (pOuterCore,"pOuterCore"),(pCores,"pCores"), (pPartGas,"pPartGas"), (force,"force"),
                            (omegaInner,"omegaInner"), (omegaGiant,"omegaGiant"), (omegaTot,"omegaTot"),
                            (kTot,"kTot"), (pTot,"pTot"), (eTot,"eTot"),
                            (angularInner,"angularInner"), (angularOuter,"angularOuter"), (angularOuter1,"angularOuter1"),
                            (angularOuter2,"angularOuter2"), (angularOuterCOM1,"angularOuterCOM1"),
                            (angularOuterCOM2,"angularOuterCOM2"), (angularOuterCOM,"angularOuterCOM"), (angularGasCOM,"angularGasCOM"),
                            (angularTot,"angularTot")], outputDir + "/graphs", beginStep,timeStep, toPlot)

def InitParser():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--beginStep', type=int,  help='first step', default=0)
    parser.add_argument('--lastStep', type=int,  help='last step', default=0)
    parser.add_argument('--timeStep', type=float,  help='time between files in days', default=0.2)
    parser.add_argument('--skip', type=int, help='number of steps to skip', default=1)
    parser.add_argument('--source_dir', type=str,  help='path to amuse files directory', default= sys.argv[0])
    parser.add_argument('--savingDir', type=str,  help='path to output directory', default= "evolution")
    parser.add_argument('--vmin', type=float,  help='minimum  density plotting', default=1e16)
    parser.add_argument('--vmax', type=float,  help='maximum  density plotting', default=1e34)
    parser.add_argument('--plot', type=lambda x: (str(x).lower() in ['true', '1', 'yes']),  help='do you want to plot profiles?', default=False)
    parser.add_argument('--axesOriginInInnerBinaryCenterOfMass', type=lambda x: (str(x).lower() in ['true', '1', 'yes']),  help='do you want to plot the inner binary at the origin?', default=False)
    parser.add_argument('--opposite', type=lambda x: (str(x).lower() in ['true', '1', 'yes']),  help='do you want the main star to be a part of the inner binary?', default=False)
    parser.add_argument('--localRadius', type=float,  help='maximum  density plotting', default=50.0)
    parser.add_argument('--cpus', type=int,  help='number of cpus', default=10)
    parser.add_argument('--massLossMethod', type=str,  help='estimated or direct', default= "estimated")
    return parser

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
        axesOriginInInnerBinaryCenterOfMass = bool(int(args[8]))
    else:
        axesOriginInInnerBinaryCenterOfMass = False
    if len(args) >9:
        opposite = bool(int(args[9]))
    else:
        opposite = False
    if len(args) > 10:
        timeStep=float(args[10])
    else:
        timeStep = 0.2
    if len(args) > 11:
        localRadius = float(args[11]) | units.RSun
    else:
        localRadius = 50.0 | units.RSun

    outputDir = savingDir + "/pics"
    return savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, plot, axesOriginInInnerBinaryCenterOfMass, opposite, timeStep, localRadius

def InitializeSnapshots(savingDir, toCompare=False, firstFile=0):
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
        dmFiles.sort(key=functools.cmp_to_key(compare))
        gasFiles.sort(key=functools.cmp_to_key(compare))
    else:
        dmFiles.sort()
        gasFiles.sort()
    numberOfCompanion = 0
    if len(dmFiles) > 0:
        try:
            numberOfCompanion = len(read_set_from_file(os.path.join(os.getcwd(), savingDir,dmFiles[firstFile]), format='amuse'))
        except:
            numberOfCompanion = len(read_set_from_file(os.path.join(os.getcwd(), savingDir,dmFiles[0]), format='amuse'))
    return gasFiles, dmFiles, numberOfCompanion

def compare(st1, st2):
    num1 = int(st1.split("_")[1].split(".")[0])
    num2 = int(st2.split("_")[1].split(".")[0])
    if num1 < num2:
        return -1
    return 1


def main(args= ["../../BIGDATA/code/amuse-10.0/runs200000/run_003","evolution",0,1e16,1e34, 1]):
    parser=InitParser()
    args=parser.parse_args()
    savingDir = os.path.join(args.source_dir, args.savingDir)
    outputDir = os.path.join(savingDir,"pics")
    toCompare = (args.savingDir != "snapshots")
    print(("plotting to " +  outputDir + " plot- " + str(args.plot) +  " from " +  args.savingDir +" begin step = " , args.beginStep , \
        " vmin, vmax = " , args.vmin, args.vmax, "special comparing = ", toCompare, "axes at the origin? ", \
        args.axesOriginInInnerBinaryCenterOfMass, "opossite? ", args.opposite, "timeStep= ", args.timeStep,
          "localRadius= ",args.localRadius))
    '''savingDir, toCompare, beginStep, lastStep, vmin, vmax, outputDir, plot, axesOriginInInnerBinaryCenterOfMass, \
        opposite, timeStep, localRadius = GetArgs(args)
    print "plotting to " +  outputDir + " plot- " + str(plot) +  " from " +  savingDir +" begin step = " , beginStep , \
        " vmin, vmax = " , vmin, vmax, "special comparing = ", toCompare, "axes at the origin? ", \
        axesOriginInInnerBinaryCenterOfMass, "opossite? ", opposite, "timeStep= ", timeStep, "localRadius= ",localRadius
    '''
    try:
        os.makedirs(outputDir)
    except(OSError):
        pass
    try:
        os.makedirs(outputDir + "/side_on")
    except(OSError):
        pass
    try:
        os.makedirs(outputDir + "/both")
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
    gasFiles, dmFiles, numberOfCompanion = InitializeSnapshots(savingDir, toCompare,args.beginStep)

    if numberOfCompanion <= 2: #binary
        print("analyzing binary")
        AnalyzeBinary(beginStep=args.beginStep,lastStep=args.lastStep, dmFiles=dmFiles, gasFiles=gasFiles,
                      savingDir=savingDir, outputDir=outputDir, vmin=args.vmin, vmax=args.vmax, toPlot=args.plot,
                      plotDust=False, timeStep=args.timeStep, skip=args.skip, cpus= args.cpus,
                      massLossMethod=args.massLossMethod)
    elif numberOfCompanion ==3: #triple
        AnalyzeTriple(beginStep=args.beginStep, lastStep=args.lastStep, dmFiles=dmFiles, gasFiles=gasFiles,
                      savingDir=savingDir, outputDir=outputDir, vmin=args.vmin, vmax=args.vmax, localRadius=args.localRadius,
                      toPlot=args.plot, opposite=args.opposite,
                      axesOriginInInnerBinaryCenterOfMass=args.axesOriginInInnerBinaryCenterOfMass, timeStep=args.timeStep)

if __name__ == "__main__":
    for arg in sys.argv:
        print(arg)
    print((len(sys.argv)))
    main(sys.argv)
