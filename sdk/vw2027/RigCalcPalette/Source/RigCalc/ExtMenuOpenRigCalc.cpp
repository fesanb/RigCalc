#include "StdAfx.h"
#include "ExtMenuOpenRigCalc.h"
#include "ExtWebPaletteRigCalc.h"

using namespace RigCalc;

namespace RigCalc
{
	static SMenuDef gMenuDef = {
		EMenuEnableFlags::DocIsActive, EMenuEnableFlags::None,
		{ "RigCalc", "open_title" }, { "RigCalc", "category" },
		{ "RigCalc", "help" }, 31, 0, 0
	};
}

// {D8F1357A-78D7-4F35-A5E4-A56392CE4D92}
IMPLEMENT_VWMenuExtension(CExtMenuOpenRigCalc, CMenuOpenRigCalc_EventSink,
	"RigCalc_OpenPalette", 1,
	0xd8f1357a, 0x78d7, 0x4f35, 0xa5, 0xe4, 0xa5, 0x63, 0x92, 0xce, 0x4d, 0x92);

CExtMenuOpenRigCalc::CExtMenuOpenRigCalc(CallBackPtr cbp)
	: VWExtensionMenu(cbp, gMenuDef, nullptr) {}

CMenuOpenRigCalc_EventSink::CMenuOpenRigCalc_EventSink(IVWUnknown* parent)
	: VWMenu_EventSink(parent) {}

void CMenuOpenRigCalc_EventSink::DoInterface()
{
	gSDK->SetWebPaletteVisibility(CExtWebPaletteRigCalc::_GetIID(), true);
	if (auto* frame = gSDK->GetWebPaletteFrame(CExtWebPaletteRigCalc::_GetIID())) {
		frame->Reload();
	}
}
