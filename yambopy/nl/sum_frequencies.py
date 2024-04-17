# Copyright (c) 2023, Claudio Attaccalite
# All rights reserved.
#
# This file is part of the yambopy project
# Calculate linear response from real-time calculations (yambo_nl)
#
import numpy as np
from yambopy.units import ha2ev,fs2aut, SVCMm12VMm1,AU2VMm1
from yambopy.nl.external_efield import Divide_by_the_Field
from yambopy.nl.harmonic_analysis import update_T_range
from tqdm import tqdm
import scipy.linalg
import sys
import os

#
# Polarization coefficient inversion see Sec. III in PRB 88, 235113 (2013) 
#
#  NW          order of the response functions 
#  NX          numer of coefficents required
#  P           real-time polarization 
#  W           multiples of the laser frequency
#  T_prediod   shorted cicle period
#  X           coefficents of the response functions X1,X2,X3...
#
def SF_Coefficents_Inversion(NW,NX,P,W1,W2,T_period,T_range,T_step,efield,tol,INV_MODE):
    #
    # Here we use always NW=NX
    #
    M_size = (2*(NW-1) + 1)**2  # Positive and negative components plut the zero
    # 
    i_t_start = int(np.round(T_range[0]/T_step)) 
    i_deltaT  = int(np.round((T_range[1]-T_range[0])/T_step)/M_size)

# Memory alloction 
    M        = np.zeros((M_size, M_size), dtype=np.cdouble)
    P_i      = np.zeros(M_size, dtype=np.double)
    T_i      = np.zeros(M_size, dtype=np.double)
    Sampling = np.zeros((M_size,2), dtype=np.double)

# Calculation of  T_i and P_i
    for i_t in range(M_size):
        T_i[i_t] = (i_t_start + i_deltaT * i_t)*T_step - efield["initial_time"]
        P_i[i_t] = P[i_t_start + i_deltaT * i_t]

    Sampling[:,0]=T_i/fs2aut
    Sampling[:,1]=P_i

# Build the M matrix
    C = np.zeros((M_size, M_size), dtype=np.int8)
    for i_t in range(M_size):
        i_c = 0
        for i_n in range(-NX+1, NX):
            for i_n2 in range(-NX+1, NX):
                M[i_t, i_c]          = np.exp(-1j * (i_n*W1+i_n2*W2) * T_i[i_t],dtype=np.cdouble)
                C[i_n+NX-1,i_n2+NX-1] = i_c
                i_c+=1

# Multiple possibilities to calculate the inversion
    INV_MODES = ['full', 'lstsq', 'svd']
    if INV_MODE not in INV_MODES:
        raise ValueError("Invalid inversion mode. Expected one of: %s" % INV_MODES)

    if INV_MODE=="full":
        try:
# Invert M matrix
            INV = np.zeros((M_size, M_size), dtype=np.cdouble)
            INV = np.linalg.inv(M)
        except:
            print("Singular matrix!!! standard inversion failed ")
            print("set inversion mode to LSTSQ")
            INV_MODE="lstsq"

    if INV_MODE=='lstsq':
# Least-squares
        I = np.eye(M_size,M_size)
        INV = np.linalg.lstsq(M, I, rcond=tol)[0]

    if INV_MODE=='svd':
# Truncated SVD
        INV = np.zeros((M_size, M_size), dtype=np.cdouble)
        INV = np.linalg.pinv(M,rcond=tol)

# Calculate X_here
    X_here=np.zeros((M_size, M_size),dtype=np.cdouble)
    for i_n in range(-NX+1, NX):
        for i_n2 in range(-NX+1, NX):
            i_c=C[i_n+NX-1,i_n2+NX-1]
            for i_t in range(M_size):
                X_here[i_n+NX-1,i_n2+NX-1]=X_here[i_n+NX-1,i_n2+NX-1]+INV[i_c,i_t]*P_i[i_t]

    return X_here,Sampling


def SF_Harmonic_Analysis(nldb, tol=1e-10, X_order=4, T_range=[-1, -1],prn_Peff=False,prn_Xhi=True,INV_MODE='svd'):
    # Time series 
    time  =nldb.IO_TIME_points
    # Time step of the simulation
    T_step=nldb.IO_TIME_points[1]-nldb.IO_TIME_points[0]
    # External field of the first run
    efield=nldb.Efield[0]
    # Numer of exteanl laser frequencies
    n_frequencies=len(nldb.Polarization)
    # Array of polarizations for each laser frequency
    polarization=nldb.Polarization

    print("\n* * * Sum/difference frequency generation: harmonic analysis * * *\n")

    freqs=np.zeros(n_frequencies,dtype=np.double)

    if efield["name"] != "SIN" and efield["name"] != "SOFTSIN" and efield["name"] != "ANTIRES":
        raise ValueError("Harmonic analysis works only with SIN or SOFTSIN fields")

    l_test_one_field=False
    if(nldb.Efield_general[1]["name"] == "SIN" or nldb.Efield_general[1]["name"] == "SOFTSIN"):
        # frequency of the second and third laser, respectively)
        pump_probe=nldb.Efield_general[1]["freq_range"][0] 
        print("Frequency of the second field : "+str(pump_probe*ha2ev)+" [eV] \b")
    elif(nldb.Efield_general[1]["name"] == "none"):
        print("Only one field present, please use standard harmonic_analysis.py for SHG,THG, etc..!")
        print("* * * Test mode with a single field * * * ")
        print(" * * * Frequency of the second field assumed to be zero * * *")
        print(" * * * Only results for SHG,THG,... are correct * * * ")
        l_test_one_field=True
        pump_probe=0.0
    else:
        raise ValueError("Fields different from SIN/SOFTSIN are not supported ! ")
    
    if(nldb.Efield_general[2]["name"] != "none"):
        raise ValueError("Three fields not supported yet ! ")

    print("Number of frequencies : %d " % n_frequencies)
    # Smaller frequency
    W_step=sys.float_info.max
    max_W =sys.float_info.min

    for count, efield in enumerate(nldb.Efield):
        freqs[count]=efield["freq_range"][0]
        if efield["freq_range"][0]<W_step:
            W_step=efield["freq_range"][0]
        if efield["freq_range"][0]>max_W:
            max_W=efield["freq_range"][0]
    print("Minimum frequency : ",str(W_step*ha2ev)," [eV] ")
    print("Maximum frequency : ",str(max_W*ha2ev)," [eV] ")
    
    # Period of the incoming laser
    T_period=2.0*np.pi/W_step
    print("Effective max time period ",str(T_period/fs2aut)+" [fs] ")

    if T_range[0] <= 0.0:
        T_range[0]=time[-1]-T_period
    if T_range[1] <= 0.0:
        T_range[1]=time[-1]
    
    T_range_initial=np.copy(T_range)

    print("Time range : ",str(T_range[0]/fs2aut),'-',str(T_range[1]/fs2aut),'[fs]')

    M_size = (2*X_order + 1)**2
    X_effective       =np.zeros((M_size,M_size,n_frequencies,3),dtype=np.cdouble)
    Sampling          =np.zeros((M_size,2,n_frequencies,3),dtype=np.double)
    Susceptibility    =np.zeros((M_size,M_size,n_frequencies,3),dtype=np.cdouble)
    
    print("Loop in frequecies...")
    # Find the Fourier coefficients by inversion
    for i_f in tqdm(range(n_frequencies)):
        #
        for i_d in range(3):
            X_effective[:,:,i_f,i_d],Sampling[:,:,i_f,i_d]=SF_Coefficents_Inversion(X_order+1, X_order+1, polarization[i_f][i_d,:],freqs[i_f],pump_probe,T_period,T_range,T_step,efield,tol,INV_MODE)

    # Calculate Susceptibilities from X_effective
    for i_order in range(-X_order,X_order+1):
        for i_order2 in range(-X_order,X_order+1):
            for i_f in range(n_frequencies):
                Susceptibility[i_order+X_order,i_order2+X_order,i_f,:]=X_effective[i_order+X_order,i_order2+X_order,i_f,:]
                if l_test_one_field:
                    Susceptibility[i_order+X_order,i_order2+X_order,i_f,:]*=Divide_by_the_Field(nldb.Efield[0],abs(i_order))
                else:
                    D2=1.0
                    if i_order!=0:
                        D2*=Divide_by_the_Field(nldb.Efield[0],abs(i_order))
                    if i_order2!=0:
                        D2*=Divide_by_the_Field(nldb.Efield[1],abs(i_order2))
                    if i_order==0 and i_order2==0: #  This case is not clear to me how we should define the optical rectification
                        D2=Divide_by_the_Field(nldb.Efield[0],abs(i_order))*Divide_by_the_Field(nldb.Efield[1],abs(i_order2))
#                    print("Order "+str(i_order)+" and "+str(i_order2)+" = "+str(D2))
                    Susceptibility[i_order+X_order,i_order2+X_order,i_f,:]*=D2

    if(prn_Peff):
        print("Reconstruct effective polarizations ...")        
        # Print time dependent polarization
        P=np.zeros((n_frequencies,3,len(time)),dtype=np.cdouble)
        for i_f in tqdm(range(n_frequencies)):
            for i_d in range(3):
                for i_order in range(-X_order,X_order+1):
                    for i_order2 in range(-X_order,X_order+1):
                        P[i_f,i_d,:]+=X_effective[i_order+X_order,i_order2+X_order,i_f,i_d]*np.exp(-1j * (i_order*freqs[i_f]+i_order2*pump_probe) * time[:])
        header2="[fs]            "
        header2+="Px     "
        header2+="Py     "
        header2+="Pz     "
        footer2='Time dependent polarization reproduced from Fourier coefficients'
        for i_f in range(n_frequencies):
            values=np.c_[time.real/fs2aut]
            values=np.append(values,np.c_[P[i_f,0,:].real],axis=1)
            values=np.append(values,np.c_[P[i_f,1,:].real],axis=1)
            values=np.append(values,np.c_[P[i_f,2,:].real],axis=1)
            output_file2='o.YamboPy-pol_reconstructed_F'+str(i_f+1)
            np.savetxt(output_file2,values,header=header2,delimiter=' ',footer=footer2)

        # Print Sampling point
        footer2='Sampled polarization'
        for i_f in range(n_frequencies):
            values=np.c_[Sampling[:,0,i_f,0]]
            values=np.append(values,np.c_[Sampling[:,1,i_f,0]],axis=1)
            values=np.append(values,np.c_[Sampling[:,1,i_f,1]],axis=1)
            values=np.append(values,np.c_[Sampling[:,1,i_f,2]],axis=1)
            output_file3='o.YamboPy-sampling_F'+str(i_f+1)
            np.savetxt(output_file3,values,header=header2,delimiter=' ',footer=footer2)


    # Print the result
    for i_order in range(-X_order,X_order+1):
        for i_order2 in range(-X_order,X_order+1):
            if i_order==0 and i_order2==0: 
                Unit_of_Measure = SVCMm12VMm1/AU2VMm1
            else:
                Unit_of_Measure = np.power(SVCMm12VMm1/AU2VMm1,abs(i_order)+abs(i_order2)-1,dtype=np.double)
                Susceptibility[i_order+X_order,i_order2+X_order,:,:]=Susceptibility[i_order+X_order,i_order2+X_order,:,:]*Unit_of_Measure
            output_file='o.YamboPy-SF_probe_order_'+str(i_order)+'_'+str(i_order2)
            if i_order == 0 or (i_order == 1 and i_order2 == 0) or (i_order == 0 and i_order2 == 1):
                header="E [eV]            X/Im(x)            X/Re(x)            X/Im(y)            X/Re(y)            X/Im(z)            X/Re(z)"
            else:
                header="[eV]            "
                header+="X/Im[cm/stV]^%d     X/Re[cm/stV]^%d     " % (abs(i_order)+abs(i_order2)-1,abs(i_order)+abs(i_order2)-1)
                header+="X/Im[cm/stV]^%d     X/Re[cm/stV]^%d     " % (abs(i_order)+abs(i_order2)-1,abs(i_order)+abs(i_order2)-1)
                header+="X/Im[cm/stV]^%d     X/Re[cm/stV]^%d     " % (abs(i_order)+abs(i_order2)-1,abs(i_order)+abs(i_order2)-1)

            values=np.c_[freqs*ha2ev]
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,0].imag],axis=1)
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,0].real],axis=1)
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,1].imag],axis=1)
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,1].real],axis=1)
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,2].imag],axis=1)
            values=np.append(values,np.c_[Susceptibility[i_order+X_order,i_order2+X_order,:,2].real],axis=1)

            footer='Non-linear response analysis performed using YamboPy'
            if prn_Xhi:
                np.savetxt(output_file,values,header=header,delimiter=' ',footer=footer)

    return Susceptibility
