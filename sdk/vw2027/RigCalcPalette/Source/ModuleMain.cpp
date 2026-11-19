//
//	ModuleMain.cpp
//
//	Main entry point for Vectorworks module code.
//


#include "StdAfx.h"
#include "RigCalc/ExtMenuOpenRigCalc.h"
#include "RigCalc/ExtWebPaletteRigCalc.h"

const char * DefaultPluginVWRIdentifier() { return "RigCalcPalette"; }


//------------------------------------------------------------------
// provide SDK version for which this plugin was compiled
extern "C" Sint32 GS_EXTERNAL_ENTRY plugin_module_ver() { return SDK_VERSION; }

//------------------------------------------------------------------
// Entry point of the module plug-in for Vectorworks
// More info at: http://developer.vectorworks.net/index.php?title=SDK:Module_Plug-in
//
extern "C" Sint32 GS_EXTERNAL_ENTRY plugin_module_main(Sint32 action, void* moduleInfo, const VWIID& iid, IVWUnknown*& inOutInterface, CallBackPtr cbp)
{
	// initialize VCOM mechanizm
	::GS_InitializeVCOM( cbp );

	Sint32	reply	= 0L;

	using namespace VWFC::PluginSupport;

	REGISTER_Extension<RigCalc::CExtMenuOpenRigCalc>( GROUPID_ExtensionMenu, action, moduleInfo, iid, inOutInterface, cbp, reply );
	REGISTER_Extension<RigCalc::CExtWebPaletteRigCalc>( GROUPID_ExtensionWebPalettes, action, moduleInfo, iid, inOutInterface, cbp, reply );

	return reply;
}
