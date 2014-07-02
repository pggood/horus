#!/usr/bin/python
# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------#
#                                                                       #
# This file is part of the Horus Project                                #
#                                                                       #
# Copyright (C) 2014 Mundo Reader S.L.                                  #
#                                                                       #
# Date: March 2014                                                      #
# Author: Carlos Crespo <carlos.crespo@bq.com>                          #
#                                                                       #
# This program is free software: you can redistribute it and/or modify  #
# it under the terms of the GNU General Public License as published by  #
# the Free Software Foundation, either version 3 of the License, or     #
# (at your option) any later version.                                   #
#                                                                       #
# This program is distributed in the hope that it will be useful,       #
# but WITHOUT ANY WARRANTY; without even the implied warranty of        #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          #
# GNU General Public License for more details.                          #
#                                                                       #
# You should have received a copy of the GNU General Public License     #
# along with this program. If not, see <http://www.gnu.org/licenses/>.  #
#                                                                       #
#-----------------------------------------------------------------------#

__author__ = u"Carlos Crespo <carlos.crespo@bq.com>"
__license__ = u"GNU General Public License v3 http://www.gnu.org/licenses/gpl.html"

import cv2
import numpy as np
from scipy import optimize  
from horus.util import profile

class Calibration:
	"""Calibration class. For managing calibration"""
	def __init__(self, parent):

		self._calMatrix=np.array([[  1.39809096e+03  , 0.00000000e+00 ,  4.91502299e+02], [  0.00000000e+00 ,  1.43121118e+03  , 6.74406283e+02], [  0.00000000e+00 ,  0.00000000e+00  , 1.00000000e+00]])
		self._calMatrixDefault=np.array([[  1.39809096e+03  , 0.00000000e+00 ,  4.91502299e+02], [  0.00000000e+00 ,  1.43121118e+03  , 6.74406283e+02], [  0.00000000e+00 ,  0.00000000e+00  , 1.00000000e+00]])
		print type(self._calMatrix)
		self._distortionVector= np.array([ 0.11892648 ,-0.24087801 , 0.01288427 , 0.00628766 , 0.01007653])
		self._distortionVectorDefault= np.array([ 0.11892648 ,-0.24087801 , 0.01288427 , 0.00628766 , 0.01007653])
		
		self._rotMatrix=np.array([[ 0.99970814 , 0.02222752 ,-0.00946474], [ 0.00930233 , 0.00739852 , 0.99992936],[ 0.02229597, -0.99972556 , 0.00718959]])
		self._rotMatrixDefault=np.array([[ 0.99970814 , 0.02222752 ,-0.00946474], [ 0.00930233 , 0.00739852 , 0.99992936],[ 0.02229597, -0.99972556 , 0.00718959]])
		
		self._transMatrix=np.array([[  -5.56044557],[  73.33950448], [ 328.54553044]])
		self._transMatrixDefault=np.array([[  -5.56044557],[  73.33950448], [ 328.54553044]])
		
		self.patternRows=11 # points_per_column
		self.patternColumns=6 # points_per_row
		self.squareWidth=12.5 # milimeters of each square's side

		self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.001)

		self.imagePointsStack=[]
		self.objPointsStack=[]

		self.objpoints=self.generateObjectPoints(self.patternColumns,self.patternRows,self.squareWidth)
		
		self.transVectors=[]

		self.centerEstimate=0,310


	def solvePnp(self,image):
		
		gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
		# the fast check flag reduces significantly the computation time if the pattern is out of sight 
		retval,corners=cv2.findChessboardCorners(gray,(self.patternColumns,self.patternRows),flags=cv2.CALIB_CB_FAST_CHECK)
		
		if retval:
			cv2.cornerSubPix(gray,corners,winSize=(11,11),zeroZone=(-1,-1),criteria=self.criteria)
			ret,rvecs,tvecs=cv2.solvePnP(self.objpoints,corners,self._calMatrix,self._distortionVector)
			self.transVectors.append(tvecs)
		else:
			print "chessboard not found :("
		return retval


	def calibrationFromImages(self):
		if hasattr(self,'rvecs'):
			del self.rvecs[:]
			del self.tvecs[:]
		ret,self._calMatrix,self._distortionVector,self.rvecs,self.tvecs = cv2.calibrateCamera(self.objPointsStack,self.imagePointsStack,self.invertedShape)
		print "Camera matrix: ",self._calMatrix
		self._distortionVector=self._distortionVector[0]
		print "Distortion coefficients: ", self._distortionVector
		print "Rotation matrix: ",self.rvecs
		print "Translation matrix: ",self.tvecs

	def detectPrintChessboard(self,image):

		gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
		self.invertedShape=gray.shape[::-1]
		retval,corners=cv2.findChessboardCorners(gray,(self.patternColumns,self.patternRows))
		if retval:
			cv2.cornerSubPix(gray,corners,winSize=(11,11),zeroZone=(-1,-1),criteria=self.criteria)
			self.imagePointsStack.append(corners)
			self.objPointsStack.append(self.objpoints)
			cv2.drawChessboardCorners(image,(self.patternColumns,self.patternRows),corners,retval)
			
		else:
			print "chessboard not found :("
		return image,retval

	def generateObjectPoints(self,patternColumns,patternRows,squareWidth):
		objp = np.zeros((patternRows*patternColumns,3), np.float32)
		objp[:,:2] = np.mgrid[0:patternColumns,0:patternRows].T.reshape(-1,2)
		objp=np.multiply(objp,12)
		return objp

	def clearData(self):
		del self.imagePointsStack[:]
		del self.objPointsStack[:]
		if hasattr(self,'rvecs'):
			del self.rvecs[:]
			del self.tvecs[:]

	def optimizeCircle(self,x2D,z2D):
		self.x2D=x2D
		self.z2D=z2D
		center,_=optimize.leastsq(self.f, self.centerEstimate)
		Ri     = self.calc_R(*center)
		return Ri,center

	def calc_R(self,xc, zc):
		return np.sqrt((self.x2D-xc)**2 + (self.z2D-zc)**2)

	def f(self,c):
		Ri = self.calc_R(*c)
		return Ri - Ri.mean()

	def updateProfileToAllControls(self):
		profile.resetProfileSetting('calibration_matrix')
		self._calMatrix=profile.getProfileSettingNumpy('calibration_matrix')

		# self._calMatrixDefault=profile.getDefaultProfileSettingNumpy('calibration_matrix')
		self._distortionVector=profile.getProfileSettingNumpy('distortion_vector')

		self._rotMatrix=profile.getProfileSettingNumpy('rotation_matrix')
		# self._rotMatrixDefault=profile.getDefaultProfileSettingNumpy('rotation_matrix')

		self._transMatrix=profile.getProfileSettingNumpy('translation_vector')		

	def restoreCalibrationMatrix(self):
		profile.resetProfileSetting('calibration_matrix')
		self._calMatrix=profile.getProfileSettingNumpy('calibration_matrix')

	def restoreDistortionVector(self):
		profile.resetProfileSetting('distortion_vector')
		self._distortionVector=profile.getProfileSettingNumpy('distortion_vector')

	def restoreRotationMatrix(self):
		profile.resetProfileSetting('rotation_matrix')
		self._rotMatrix=profile.getProfileSettingNumpy('rotation_matrix')

	def restoreTranslationVector(self):
		profile.resetProfileSetting('translation_vector')
		self._transMatrix=profile.getProfileSettingNumpy('translation_vector')

	def saveCalibrationMatrix(self):
		profile.putProfileSetting('calibration_matrix',self._calMatrix)

	def saveDistortionVector(self):
		profile.putProfileSetting('distortion_vector',self._distortionVector)

	def saveRotationMatrix(self):
		profile.putProfileSetting('rotation_matrix',self._rotMatrix)
		print profile.getProfileSettingNumpy('rotation_matrix')

	def saveTranslationVector(self):
		profile.putProfileSetting('translation_vector',self._transMatrix)