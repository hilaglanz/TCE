import pickle
import os

from amuse.units import units
from amuse.units.units import *
from amuse.plot import native_plot, sph_particles_plot
from amuse.ext.star_to_sph import pickle_stellar_model
from amuse.datamodel import Particles
from amuse.io import read_set_from_file
import StarModels
import EvolveNBody



def CreateTripleSystem(configurationFile, savedPath = "", takeSavedSPH = False, takeSavedMesa = False):
    '''
    creating the TCE
    :return:main star's mass, the envelope particles, the core particles, the binary stars and the triple semmimajor
    '''
    giant = StarModels.CreatePointStar(configurationFile,configurationSection="MainStar")
    innerBinary = StarModels.Binary(configurationFile, configurationSection="InnerBinary")

    #now setting up the giant (want it to be relaxed and spinning)
    outerBinary = StarModels.Binary(configurationFile, configurationSection="OuterBinary")
    #notice that the giant is the binary.stars[0], the companions are the next

    innerBinary.stars.position += outerBinary.stars[1].position
    innerBinary.stars.velocity += outerBinary.stars[1].velocity

    giant.position = innerBinary[0].position
    giant.velocity = innerBinary[0].velocity

    triple = innerBinary.stars
    giantInSet = triple.add_particle(giant)

    triple.move_to_center()
    innerBinary.stars = triple - giantInSet

    sphStar = StarModels.SphStar(giantInSet,configurationFile,configurationSection="MainStar",
                                savedMesaStarPath = savedPath, takeSavedMesa=takeSavedMesa)
    print "Now having the sph star and the binaries, ready for relaxing"
    starEnvelope, dmStars = EvolveNBody.Run(totalMass= giantInSet.mass + innerBinary.stars.total_mass(),
                    semmiMajor= outerBinary.semimajorAxis, sphEnvelope= sphStar.gas_particles, sphCore=sphStar.core_particle,
                                             stars=innerBinary, endTime= sphStar.relaxationTime,
                                             timeSteps= sphStar.relaxationTimeSteps, relax=True,
                                              numberOfWorkers= sphStar.numberOfWorkers, savedVersionPath=savedPath, saveAfterMinute=10)
    starCore = dmStars[-1]
    starCore.radius = sphStar.core_particle.radius

    #moving the main star back to the center
    diffPosition = starCore.position - giantInSet.position
    diffVelocity = (starCore.velocity*starCore.mass + starEnvelope.center_of_mass_velocity() * starEnvelope.total_mass())/ giant.mass
    starEnvelope.position -= diffPosition
    starCore.position -= diffPosition
    starEnvelope.velocity -= diffVelocity
    starCore.velocity -= diffVelocity
    dmStars[-1]= starCore

    sphMetaData = StarModels.SphMetaData(sphStar)

    #saved state
    StarModels.SaveState(savedPath, starEnvelope.total_mass() + starCore.mass, starEnvelope, dmStars, outerBinary.semimajorAxis, sphMetaData)

    return giant.mass, starEnvelope, starCore, innerBinary, outerBinary.semimajorAxis, sphMetaData



def Start(savedVersionPath = "Glanz/savings/TCE/0511_0511/100000", takeSavedState = "False", step = -1, configurationFile = "Glanz/TCEConfiguration.ini"):
    '''
    This is the main function of our simulation
    :param savedVersionPath: path to the saved state
    :param takeSavedState: do you have a saved state you want to use? True or False if it is all saved right before the evolution, 
			    Relax if its in the middle of the relaxation, Evolve if its in the evolutionProcess,
                            Mesa if its only the Mesa Star
    :return: None
    '''
    try:
        os.makedirs(savedVersionPath + "/pics")
    except(OSError):
        pass
    # creating the triple system
    if takeSavedState == "True":
        starMass, starEnvelope, starCore, binary, tripleSemmimajor, sphMetaData = \
            StarModels.TakeTripleSavedState(savedVersionPath, configurationFile, step= -1)
    elif takeSavedState == "Evolve":
        starMass, starEnvelope, starCore, binary, tripleSemmimajor,sphMetaData = \
            StarModels.TakeTripleSavedState(savedVersionPath + "/evolution", configurationFile, step)
    else:
        if takeSavedState == "Mesa":
            starMass, starEnvelope, starCore, binary, tripleSemmimajor, sphMetaData = CreateTripleSystem(configurationFile, savedVersionPath, takeSavedMesa= True)
        else:
            starMass, starEnvelope, starCore, binary, tripleSemmimajor, sphMetaData = CreateTripleSystem(configurationFile, savedVersionPath)

    # creating the NBody system with the 3 and evolving



    EvolveNBody.Run(totalMass= starMass + binary.stars.total_mass(),
                    semmiMajor= tripleSemmimajor, sphEnvelope= starEnvelope,
                    sphCore=starCore, stars=binary,
                    endTime= sphMetaData.evolutionTime, timeSteps= sphMetaData.evolutionTimeSteps, numberOfWorkers= sphMetaData.numberOfWorkers, step= step,
                    savedVersionPath=savedVersionPath, saveAfterMinute= 0)

    print "****************** Simulation Completed ******************"
if __name__ == "__main__":
    Start(takeSavedState="Mesa")

