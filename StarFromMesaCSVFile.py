import os
from amuse.datamodel import *
from amuse.community.mesa.interface import MESA
from amuse.units import constants

def ParseCSV(filePath):
    print "**"
    dictionary = dict()
    with open(filePath) as csvFile:
        headers = csvFile.readline().replace('\n','').split(", ")
        print '---------------'
        print len(headers)
        fieldsCount = len(headers)
        for line in csvFile.readlines():
            fields = line.split(" ")
            for i in xrange(fieldsCount):
                if headers[i] not in dictionary.keys():
                    dictionary[headers[i]] = []
                dictionary[headers[i]].append(float(fields[i]))
        if "mass" not in headers:
            dictionary["mass"] = [0.6] | units.MSun
        if "luminosity" not in headers:
            dictionary["luminosity"] = [(constants.four_pi_stefan_boltzmann * (dictionary["radius"][i] |units.cm) ** 2
                                        * (dictionary["temperature"][i] |units.K) ** 4).value_in(units.LSun) for i in xrange(len(dictionary["temperature"]))]

    return dictionary

def CreateDeafultValueArray(value, length):
    a = []
    for i in xrange(length):
        a.append(value)
    return a

def AddUnits(dictionary):
    internal_structure = dict()
    #internal_structure['radius'] = internal_structure['radius'] | units.m
    print dictionary['radius'][0]
    internal_structure['radius'] = dictionary['radius'] | units.cm
    print dictionary['mass'][0]
    print dictionary['luminosity'][0]
    internal_structure['mass'] = dictionary['mass']
    internal_structure['rho'] =dictionary['rho'] | units.g/units.cm **3
    internal_structure['temperature'] = dictionary['temperature'] | units.K
    internal_structure['X_H'] = dictionary['X_H']
    internal_structure['luminosity'] = dictionary['luminosity'] | units.LSun
    #internal_structure['luminosity'] = internal_structure['luminosity'] | units.LSun
    internal_structure['X_He'] = dictionary['X_He']
    internal_structure['X_C'] = dictionary['c12']
    internal_structure['X_N'] = dictionary['X_N']
    internal_structure['X_O'] = dictionary['o16']
    internal_structure['X_Ne'] = dictionary['X_Ne']
    internal_structure['X_Mg'] = dictionary['X_Mg']
    internal_structure['X_Si'] = dictionary['X_Si']
    internal_structure['X_Fe'] = [0.0 for element in internal_structure['X_Si']]

    return internal_structure

def CompleteStellarDictionary(dictionary):
    stellar_structure = dictionary
    keys = ['radius','rho','temperature','luminosity','X_H','X_He','X_C','X_N','X_O','X_Ne','X_Mg','X_Si','X_Fe']
    for key in keys:
        if key not in dictionary.keys():
            stellar_structure[key] = CreateDeafultValueArray(0.0,len(dictionary["temperature"]))

    return stellar_structure

def derive_stellar_structure(internal_structure):
        stellar_model = Grid()
        stellar_model.dmass = internal_structure['dmass']
        stellar_model.mass = stellar_model.dmass.accumulate()
        stellar_model.rho = internal_structure['density']
        stellar_model.radius = internal_structure['radius']
        stellar_model.temperature = internal_structure['temperature']
        stellar_model.luminosity = internal_structure['luminosity']
        setattr(stellar_model, 'X_H', internal_structure['X_H'])
        setattr(stellar_model, 'X_He', internal_structure['X_He'])
        setattr(stellar_model, 'X_C', internal_structure['c12'])
        setattr(stellar_model, 'X_N', internal_structure['X_N'])
        setattr(stellar_model, 'X_O', internal_structure['o16'])
        setattr(stellar_model, 'X_Ne', internal_structure['X_Ne'])
        setattr(stellar_model, 'X_Mg', internal_structure['X_Mg'])
        setattr(stellar_model, 'X_Si', internal_structure['X_Si'])
        setattr(stellar_model, 'X_Fe', numpy.zeros(len(stellar_model.dmass)))
        return stellar_model

def GetStar(csvPath):
    code = MESA()
    code.initialize_code()
    code.parameters.stabilize_new_stellar_model_flag = False
    code.commit_parameters()
    d = ParseCSV(csvPath)
    dictionary = CompleteStellarDictionary(d)
    internal_structure = AddUnits(dictionary)
    star = code.new_particle_from_model(internal_structure, 1000.0 | units.Myr)
    number_of_zones = code.particles[0].get_number_of_zones()
    composition = code.particles[0].get_chemical_abundance_profiles(number_of_zones = number_of_zones)
    print code.particles[0].get_temperature_profile()
    print code.particles
    return star

if __name__ == "__main__":
    star = GetStar("/home/hilaglanz/Downloads/star_model06Co.csv")
    print star.mass


