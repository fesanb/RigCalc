#pragma once

namespace RigCalc
{
	using namespace VWFC::PluginSupport;
	class CMenuOpenRigCalc_EventSink : public VWMenu_EventSink
	{
	public:
		explicit CMenuOpenRigCalc_EventSink(IVWUnknown* parent);
		virtual void DoInterface() override;
	};
	class CExtMenuOpenRigCalc : public VWExtensionMenu
	{
		DEFINE_VWMenuExtension;
	public:
		explicit CExtMenuOpenRigCalc(CallBackPtr cbp);
	};
}
