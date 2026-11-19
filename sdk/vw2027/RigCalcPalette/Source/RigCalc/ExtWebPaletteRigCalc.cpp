#include "StdAfx.h"
#include "ExtWebPaletteRigCalc.h"
#include "PaletteSnapshotProvider.h"

using namespace RigCalc;

// {6B213C9E-757D-4B78-9B8E-8EF32D1D52C4}
IMPLEMENT_VWPaletteExtension(CExtWebPaletteRigCalc,
	"RigCalc_Palette", 1,
	0x6b213c9e, 0x757d, 0x4b78, 0x9b, 0x8e, 0x8e, 0xf3, 0x2d, 0x1d, 0x52, 0xc4);

CExtWebPaletteRigCalc::CExtWebPaletteRigCalc(CallBackPtr /* cbp */)
	: VWExtensionWebPalette("html", "index.html")
{
}

void CExtWebPaletteRigCalc::DefineSinks()
{
	DefineSink<CPaletteSnapshotProvider>(VectorWorks::Extension::IID_WebJavaScriptProvider);
}

TXString VCOM_CALLTYPE CExtWebPaletteRigCalc::GetTitle()
{
	return "RigCalc";
}

bool VCOM_CALLTYPE CExtWebPaletteRigCalc::GetInitialSize(ViewCoord& outCX, ViewCoord& outCY)
{
	outCX = 420;
	outCY = 620;
	return true;
}

bool VCOM_CALLTYPE CExtWebPaletteRigCalc::GetMinimalSize(ViewCoord& outCX, ViewCoord& outCY)
{
	outCX = 320;
	outCY = 360;
	return true;
}
