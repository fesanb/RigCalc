#pragma once

namespace RigCalc
{
	using namespace VWFC::PluginSupport;

	class CExtWebPaletteRigCalc : public VWExtensionWebPalette
	{
		DEFINE_VWPaletteExtension;
	public:
		explicit CExtWebPaletteRigCalc(CallBackPtr cbp);

		virtual void DefineSinks() override;
		virtual TXString VCOM_CALLTYPE GetTitle() override;
		virtual bool VCOM_CALLTYPE GetInitialSize(ViewCoord& outCX, ViewCoord& outCY) override;
		virtual bool VCOM_CALLTYPE GetMinimalSize(ViewCoord& outCX, ViewCoord& outCY) override;
	};
}
