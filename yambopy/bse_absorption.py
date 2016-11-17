# Copyright (c) 2015, Henrique Miranda
# All rights reserved.
#
# This file is part of the yambopy project
#
from yambopy import *
from yambopy.plot  import *
import os

class YamboBSEAbsorptionSpectra(YamboSaveDB):
    """
    Create a file with information about the excitons from Yambo files
    """
    def __init__(self,job_string,path='.'):

        #look for the save folder
        self.save=path+'/SAVE'
        if not os.path.isdir(self.save):
            raise ValueError('SAVE folder not found in %s'%self.save)

        YamboSaveDB.__init__(self,save=self.save)

        self.job_string = job_string
        self.data = {"excitons":[],
                     "lattice": self.lat,
                     "atypes": self.atomic_numbers,
                     "atoms": self.atomic_positions}

        self.atoms = None
        self.excitons = None

        #use YamboOut to read the absorption spectra
        self.path = path
        y = YamboOut(path)

        # we obtain all the bse spectra
        absorptionspectra = y.get_data(('eps','diago'))
        if absorptionspectra == {}:
           raise ValueError('Could not find the o-*diago*eps file. Make sure you diagonalized the BSE hamiltonian in yambo.')  

        #we just use one of them
        key = list(absorptionspectra)[0]
        for key,value in absorptionspectra[key].items():
            self.data[key] = value

    def get_excitons(self,min_intensity=0.1,max_energy=4,Degen_Step=0.0):
        """ 
        Obtain the excitons using ypp
        Parameters:
            min_intensity - Only plot excitons with intensity larger than this value (default: 0.1)
            max_energy    - Only plot excitons with energy below this value (default: 4 eV)
            Degen_Step    - Only plot excitons whose energy is different by more that this value (default: 0.0)
        """
        filename = "%s/o-%s.exc_E_sorted"%(self.path,self.job_string)
        if not os.path.isfile(filename):
            os.system("cd %s; ypp -e s -J %s"%(self.path,self.job_string))
        self.excitons = np.loadtxt(filename)

        #filter with degen
        if Degen_Step:
            new_excitons = []
            prev_exc = 0
            for exc in self.excitons:
                e,i,index = exc
                if abs(e-prev_exc)>Degen_Step:
                    new_excitons.append(exc)
                prev_exc = e
            self.excitons = np.array(new_excitons)

        #filter with energy
        self.excitons = self.excitons[self.excitons[:,0]<max_energy]

        #filter with intensity
        self.excitons = self.excitons[self.excitons[:,1]>min_intensity]

        return self.excitons

    def get_wavefunctions(self, FFTGvecs=30,
                          Cells=[1,1,1], Hole=[0,0,0],
                          Direction="123", Format="x",
                          Degen_Step=0.0100,
                          repx=range(-1,2), repy=range(-1,2), repz=range(-1,2),
                          wf=False):
        """
        Collect all the wavefuncitons with an intensity larger than self.threshold
        Parameters:
          FFTGvecs   - Number of FFTGvecs. Related to how accurate the representation is
          Cells      - Number of cells to plot in real space
          Hole       - Define the hole position in cartesian coordinates
          Direction  - Choose the directions to plot along
          Format="x" - Choose the format to plot in. Can be: x for xcrysden or g for gnuplot
          Degen_Step - Threshold to merge degenerate states. If the difference in energy between the states is smaller than
                       this value their wavefunctions will be plotted together
          repx       - Number or repetitions along the x direction
          repy       - Number or repetitions along the x direction
          repz       - Number or repetitions along the x direction
          wf         - Get the wavefuncitons in real space or not (default: False)
        """
        if self.excitons is None:
            raise ValueError( "Excitons not present. Run YamboBSEAbsorptionSpectra.get_excitons() first" )

        #create a ypp file using YamboIn for reading the wavefunction
        yppwf = YamboIn('ypp -e w',filename='ypp.in',folder=self.path)
        yppwf['Format'] = Format
        yppwf['Direction'] = Direction
        yppwf['FFTGvecs'] = FFTGvecs
        yppwf['Degen_Step'] = Degen_Step
        yppwf['Hole'] = [Hole,'']
        yppwf['Cells'] = [Cells,'']

        #create a ypp file using YamboIn for reading the excitonic weights
        yppew = YamboIn('ypp -e a',filename='ypp.in',folder=self.path)
        yppew['MinWeight'] = 1e-6
        yppew['Degen_Step'] = Degen_Step

        keywords = ["lattice", "atoms", "atypes", "nx", "ny", "nz"]
        for exciton in self.excitons:
            #get info
            e,intensity,i = exciton

            if wf:
                ##############################################################
                # Excitonic Wavefunction
                ##############################################################
                #create ypp input for the wavefunction file and run
                yppwf["States"] = "%d - %d"%(i,i)
                yppwf.write("yppwf_%d.in"%i)

                filename = "o-%s.exc_%dd_%d%s"%(self.job_string,len(Direction),i,{"g":"","x":".xsf"}[Format] )
                if not os.path.isfile(filename):
                    os.system("cd %s; ypp -F yppwf_%d.in -J %s"%(self.path,i,self.job_string))

                #read the excitonic wavefunction
                if Format == 'x':
                    ewf = YamboExcitonWaveFunctionXSF()
                else:
                    ewf = YamboExcitonWaveFunctionGnuplot()
                ewf.read_file(filename)
                data = ewf.get_data()
                for word in keywords:
                    if word in data:
                        self.data[word] = data[word]

            ##############################################################
            # Excitonic Amplitudes
            ##############################################################
            #create ypp input for the amplitudes file and run
            yppew["States"] = "%d - %d"%(i,i)
            yppew.write("%s/yppew_%d.in"%(self.path,i))

            filename = "%s/o-%s.exc_weights_at_%d"%(self.path,self.job_string,i)
            if not os.path.isfile(filename):
                os.system("cd %s; ypp -F yppew_%d.in -J %s"%(self.path,i,self.job_string))

            #read the excitonic weigths
            ew = YamboExcitonWeight(filename,save=self.save,path=self.path)
            qpts, weights = ew.calc_kpts_weights(repx=repx,repy=repy,repz=repz)

            ############
            # Save data
            ############
            exciton = {"energy": e,
                       "intensity": intensity,
                       "weights": weights,
                       "qpts": qpts,
                       "index": i}
            if wf:
                exciton["hole"] = Hole
                exciton["datagrid"] = np.array(data["datagrid"])

            self.data["excitons"].append(exciton)

    def write_json(self):
        """ Write a jsonfile with the absorption spectra and the wavefunctions of certain excitons
        """
        print "writing json file...",
        JsonDumper(self.data,"absorptionspectra.json")
        print "done!"
