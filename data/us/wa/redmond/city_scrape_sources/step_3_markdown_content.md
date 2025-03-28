<script>jQuery(document).click(function (event) { var target = jQuery(event.target); if (target.attr('src') && target.parents('.image').length && target.parents('.widget').length) { var text = target.attr('title');  if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Image', eventAction: 'Image - ' + text, eventLabel: window.location.href }); } if (target.is('button') || target.hasClass('button') || target.parents().hasClass('button')) { var text = ""; if (target.parents('.button')[0]) { text = target.parents('.button').first().text(); } else if (target.text().length) { text = target.text(); } else if (target.attr('title').length) { text = target.attr('title'); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Button', eventAction: 'Button - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetCustomHtml').length) { ga('send', { hitType: 'event', eventCategory: 'Custom Html', eventAction: 'Custom Html Clicked', eventLabel: window.location.href }); } if (target.parents('.editor').length) { ga('send', { hitType: 'event', eventCategory: 'Editor', eventAction: 'Editor Link Clicked', eventLabel: window.location.href }); } if (target.parents('.GraphicLinks').length) { var text = ""; var targetGraphicLink = target; if (target.hasClass('widgetGraphicLinksLink')) { targetGraphicLink = jQuery(target.children()[0]); } if (targetGraphicLink.hasClass('text')) { text = targetGraphicLink.text(); } else if (targetGraphicLink.attr('src').length) { if (targetGraphicLink.attr('alt').length) { text = targetGraphicLink.attr('alt'); } else { text = targetGraphicLink.attr('src'); } } else { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Graphic Links', eventAction: 'Graphic Link - ' + text, eventLabel: window.location.href }); } if (target.parents('.InfoAdvanced').length) { ga('send', { hitType: 'event', eventCategory: 'Info Advanced', eventAction: 'Info Advanced Clicked', eventLabel: window.location.href }); } if (target.parents('.list').length) { ga('send', { hitType: 'event', eventCategory: 'List', eventAction: 'List Clicked', eventLabel: window.location.href }); } if (target.parents('.megaMenuItem').length || target.parents('.topMenuItem').length) { var megaMenuText = jQuery('.topMenuItem.mouseover').find('span').text(); var breadCrumbs = []; jQuery('.breadCrumbs > li').each(function () {  breadCrumbs.push(this.textContent); }); var pageTitle = breadCrumbs.join('>'); var subTitleText = target.parents('.megaMenuItem').children('.widgetTitle').children().text(); var text = ""; if (pageTitle) { text += pageTitle + " | "; } else { text += document.title + ' - '; } if (target.text() == "" && megaMenuText == "") { text += "N/A"; } else if (target.text().length && megaMenuText.length) { if (megaMenuText == target.text()) { text += megaMenuText; } else { text += megaMenuText + " - " + subTitleText + " - " + target.text(); } } else if (target.text() == "") { text += megaMenuText; } else { text += target.text(); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Mega Menu', eventAction: 'Mega Menu : ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetNewsFlash').length && target.parents('.widgetItem').length) { var text = jQuery(target.parents('.widgetItem')[0]).find('.widgetTitle').children().text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'News Flash', eventAction: 'News Flash - ' + text, eventLabel: window.location.href }); } if (target.hasClass('widgetQuickLinksLink') || target.find('.widgetQuickLinksLink').length) { var text = target.text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Quick Links', eventAction: 'Quick Links - ' + text, eventLabel: window.location.href }); } if (target.attr('src') && target.parents('.cpSlideshow').length) { var text = target.attr('title'); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Slideshow', eventAction: 'Slideshow - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetText').length) { ga('send', { hitType: 'event', eventCategory: 'Text', eventAction: 'Text Link Clicked', eventLabel: window.location.href }); }});</script>  [Skip to Main Content](https://redmond.gov/CivicAlerts.aspx?AID=2239#contentarea)   [![Emergency Alert](images/95ea8d33903793c038d8e67c5ae2578b154b250e6054a7950906f9bd965becfc)Info](https://redmond.gov/2241)   [Immigration ResourcesClick for more information](https://redmond.gov/AlertCenter.aspx?AID=Immigration-Resources-78)   [![Redmond Washington Homepage](images/221c85f61d5f28f32c5ff33002f35480d168654753fe3a9a659abd04f8cd5b45)](https://redmond.gov/CivicAlerts.aspx?AID=2239)  

 1.  [News](https://redmond.gov/CivicAlerts.aspx?AID=2239) 
 1.  [I Want To...](https://redmond.gov/9/I-Want-To) 
 1.  [Community](https://redmond.gov/101/Community) 
 1.  [Business](https://redmond.gov/35/Business) 
 1.  [Government](https://redmond.gov/27/Government) 
<script type="text/javascript"> document.addEventListener('DOMContentLoaded',function () { var menuID = 'mainNavMenu'; var menuType = MAIN_MENU; //setup menu manager properties for main menu if (!menuManager.mobileMainNav && true) menuManager.adjustMainItemsWidth('#' + menuID); menuManager.isMainMenuEditable = false; menuManager.mainMenuMaxSubMenuLevels = 4; menuManager.setMOMMode(2, menuType); //Init main menu var setupDraggable = menuManager.isMainMenuEditable; var urlToGetHiddenMenus = '/Pages/MenuMain/HiddenMainSubMenus?pageID=1&moduleID=1&themeID=57&menuContainerID=mainNav'; menuManager.setupMenu(menuID, 'mainNav', menuType, setupDraggable, urlToGetHiddenMenus); menuManager.mainMenuInit = true; menuManager.mainMenuTextResizer = true; if (1.00 > 0) menuManager.mainMenuTextResizerRatio = 1.00; if (window.isResponsiveEnabled) menuManager.mainMenuReady.resolve(); }); </script> <script async="" src="https://cse.google.com/cse.js?cx=001121890526140639040:zh3by1d9q84"></script>  []()  []()  <script type="text/javascript"> $(window).on("load", function () { $.when(window.Pages.rwdSetupComplete).done(function () { renderExternalBannerSlideshow('banner1', {"BannerOptionID":712,"ThemeID":57,"SlotName":"banner1","Name":"Default","IsDefault":true,"BannerMode":2,"SlideShowSlideTiming":"5","SlideshowTransition":0,"SlideShowTransitionTiming":"1","ImageScale":true,"ImageAlignment":1,"ImageScroll":true,"MuteSound":true,"VideoType":0,"Status":40,"SlideshowControlsPosition":0,"SlideshowControlsAlignment":0,"SlideshowBannerControlsColorScheme":0,"DisplayVideoPauseButton":false,"VideoPauseButtonAlignment":1,"VideoPauseButtonControlsAlignment":0,"VideoPauseButtonStyle":"#FFFFFF","VideoPauseButtonBackgroundStyle":"#000000","VideoPauseButtonAlignmentClass":"alignRight viewport","DisplaySlideshowPauseButton":false,"SlideshowControlsColor":"#FFFFFF","SlideshowControlsBackgroundColor":"#000000","SlideshowPauseButtonClass":"isHidden","BannerImages":[{"BannerImageID":954,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36208","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":1,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":955,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36209","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":2,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":956,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36210","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":3,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":957,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36211","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":4,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""}],"BannerVideos":[],"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/"}, '/App_Themes/2025 - Simple/Images/', 'Rotating'); }); }); </script> 

 1.  [Home](https://redmond.gov/CivicAlerts.aspx?AID=2239) 
 1. News Flash
 <script type="text/javascript"><!-- var isie6 = false, isie7 = false, isie6or7 = false; var intCountryCode = 840; function setUrlLength(editor) { //Toggle Image Context Menu Items setMenuItems(editor); //setContentBackgroundColor(editor); removeIEParagraphs(editor); } function setUrlLengthAndToolToggle(editor) { var minToolsGroups = 2; // Number of MinimumSetOfTools tools groups.  // Hide the MinimumSetOfTools on load. var toolbar = editor.get_toolContainer(); // Get toolbar container. var toolgroups = toolbar.getElementsByTagName("UL"); // Get all toolgroups containers.  for (var i = toolgroups.length - 1; i >= minToolsGroups; i--) toolgroups[i].style.display = "none";  if (editor.isIE) { var elem = editor.get_element(); elem.style.height = "430px";  elem.style.minHeight = "430px"; }  // Toggle Image Context Menu Items. setMenuItems(editor); //setContentBackgroundColor(editor); removeIEParagraphs(editor); }//--></script><script src="/ScriptResource.axd?d=kB9kqJ8G5bbVUkLIbkM_oWnWnbqKfmnijNvsGOdktAJN6X3E4IB1Ohim-XfL1bXqyhvHpFA6calISmsC9Do0K1jLgqaX5q7C12oYcoh4sn7Rb0pnPcc8nqSRG7UU7_90wNYn3HODMfqBMb-_fPUnBOi0lNqIP-V5iT54maOgYENrXw1cY5S_BKzgEKHC0oaJ0c8919qI0FCmCP3OGvShdDSMG4Ugcx-gfnVT0scxcMGBbz99a6uiw_3nP-VsLsbWwdhtEpb7o0k09629luJjVJub_8Rxcey54Z4TXug-4PjZv-2tKlkixzjql8wiTe4mP9VgLO1pXyY20BKVwpRkD8OErQCEy_Ncn6XLVZRKhBUKaUh-qSShvq5dwhcOEfDuDbOk8K0LNIDT19SrfEiL3OEOre_183ge7-WreFhCnLbba8t7J3g_GxHH8h6_tiPN_-sv0gX-93CSvG6Zro_ES91NsNKn1vvoKHK9qmyw1MAU91rxqlCtoXJAtqpKcMih1HIupSwbnYeMdZ6WQIxsvNNHhpfuoMjaur6u0VrYAmtJYIAA2XtF1-Rsw64yk136yplYJFNKndmGvYDrPOdAWr62DbwZfVZ0k-dKZ9uE56dzOQRCS5g5PTU62iFnnXQeQqWDKMBuATfJcBvKIZDkIrS0ohTWuIz-eq7xXKyWjASPArtOIPELf8w9wDA7qDwkPgnLpAGgAzXAwtqw7bD5dGnOSIW6N8GqF8FNjXdMlF_GdxSUMh_T6pAa_T_pstGGOpVUyg36NnlrD6f1VhWq9bzb05Ix0kPiXJcxFHrAF3BqLEHInjYE9CXuhVA_tCSbNS-teTycuhdXs3AZmB5iHvpvdvtAzKYttSC4rR39Ip01" type="text/javascript"></script><script type="text/javascript"> Sys.WebForms.PageRequestManager.getInstance().add_beginRequest(beginRequest); Sys.WebForms.PageRequestManager.getInstance().add_pageLoaded(pageLoaded); </script> <script src="/1757422876.js" type="text/javascript"></script> 

### Module Search

 Enter Search Terms All categoriesHomeParks & RecRedmond Police BlotterEnvironmentNews ReleasesCommunity Resources and Servicescp-testRedmond in the News

### Tools

 1.  [RSS](https://redmond.gov/rss.aspx#rssCivicAlerts) 
 1.  [Notify Me®](https://redmond.gov/civicalerts.aspx?Mode=Subscribe) 
 1. 

### Categories

 1.  [All Categories](https://redmond.gov/CivicAlerts.aspx) 
 1.  [Home](https://redmond.gov/CivicAlerts.aspx?CID=1) 
 1.  [Parks & Rec](https://redmond.gov/CivicAlerts.aspx?CID=7) 
 1.  [Redmond Police Blotter](https://redmond.gov/CivicAlerts.aspx?CID=8) 
 1.  [Environment](https://redmond.gov/CivicAlerts.aspx?CID=10) 
 1.  [News Releases](https://redmond.gov/CivicAlerts.aspx?CID=11) 
 1.  [Community Resources and Services](https://redmond.gov/CivicAlerts.aspx?CID=12) 
 1.  [cp-test](https://redmond.gov/CivicAlerts.aspx?CID=13) 
 1.  [Redmond in the News](https://redmond.gov/CivicAlerts.aspx?CID=14) 

# News Flash

## Home

 Posted on: October 21, 2024 

### Learn How Mayor Birney is Enhancing Her Leadership

  ![Learn How Mayor Birney is Enhancing Her Leadership News Flash](images/0c083207b284619d7771566a41986a995b8d81f7cea1d482bbf7e01ce26734b1)  

Mayor Birney recently earned an Advanced Certificate of Municipal Leadership from the Association of Washington Cities (AWC) for her service on the board of Hopelink. AWC’s Certificate of Municipal Leadership program recognizes city and town elected officials for accomplishing training in five core areas: 

 * Roles, responsibilities, and legal requirements
 * Public sector resource management
 * Community planning and development
 * Effective local leadership
 * Diversity, equity, inclusion, and belonging 

Those who earn the advanced certificate have continued to strive for excellence by attending conferences and trainings, serving their community, and further developing leadership skills.  

  [Learn about AWC](https://www.facebook.com/AWCities/?utm_medium=email&utm_source=govdelivery)   [![Facebook](images/0016a2ca28609c8dd805c52a747c28bcbfb0c01eaf94356b74d07d4b1ddbfaa2.png)](https://www.facebook.com/sharer/sharer.php?u=https%3a%2f%2fwww.redmond.gov%2fCivicAlerts.aspx%3fAID%3d2239&t=Check out this news article for Redmond, WA)  [![Twitter](images/8819083ae48b384cff983f9b17c4164e93cc668a49249a76ab40401f1c3d18bd.png)](https://twitter.com/share?url=https%3a%2f%2fwww.redmond.gov%2fCivicAlerts.aspx%3fAID%3d2239&text=Check out this news article for Redmond, WA)  [![Email](images/903533200ecbceaa8dc3167f193cf33bb7dfa0cff639d9f28d86221d4745ae73.png)](https://redmond.gov/CivicAlerts.aspx?AID=2239#) <script language="javascript" type="text/javascript" src="/Assets/Scripts/SocialShare.js"></script><script language="javascript" type="text/javascript"> $(document).ready(function () { var socialShareJs = new SocialShare(); socialShareJs.setup('Check out this news article for Redmond, WA', 'https://www.redmond.gov/CivicAlerts.aspx?AID=2239'); }); </script>  [⇐PreviousFall Back and Change Your Batteries](https://redmond.gov/CivicAlerts.aspx?AID=2241)  [Next⇒City Council Vice President Jessica Forsythe Named Co-Chair of Eastrail](https://redmond.gov/CivicAlerts.aspx?AID=2238)  

## Other News in Home

  [![Mayor Birney Joins Greater Seattle Partners Board News Flash](images/c6975bcc890de3d076bea5f0fb31b6b9b97454f911ffb571874aa1bc3b6d101a)](https://www.redmond.gov/CivicAlerts.aspx?AID=2452) 

###  [Mayor Birney Joins Greater Seattle Partners Board](https://www.redmond.gov/CivicAlerts.aspx?AID=2452) 

 Posted on: March 24, 2025  [![Power Your Home with Solar News Flash](images/c9e8b486414fec7b2ab7f62e658d62e34faf7de00eb90d06b7eeba78fd09d287)](https://olysol.org/solarize/eastside/?utm_medium=email&utm_source=govdelivery) 

###  [Power Your Home with Solar](https://olysol.org/solarize/eastside/?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 24, 2025  [![Have an Egg-cellent Time News Flash](images/b2f8d664f9fe2e9719c840b95195c02c4d1c45720c1a149d62b5e85bb3e7d19e)](https://app.amilia.com/store/en/city-of-redmond/shop/activities/5584291) 

###  [Have an Egg-cellent Time](https://app.amilia.com/store/en/city-of-redmond/shop/activities/5584291) 

 Posted on: March 24, 2025  [![Summer Activities News Flash](images/e7a1452230226a54a8dddd3e9e826ba4e1afa4c37ad96b59a90e49a535a7bc07)](https://www.redmond.gov/1156/Summer-Camps) 

###  [Register for Summer Activities](https://www.redmond.gov/1156/Summer-Camps) 

 Posted on: March 24, 2025  [![Redmond Firefighters Climb for a Cure News Flash](images/644105b325c9cbf90da91f4c42408b37b77df5f644d601bb748132756f020ab3)](https://www.lls.org/mission) 

###  [Redmond Firefighters Climb for a Cure](https://www.lls.org/mission) 

 Posted on: March 24, 2025  [![Ride the 2 Line to Marymoor Village and Downtown Redmond](images/fde8ac21a4569114202d45d1e414e1787f7e2f43af808b1c41ea1645eb72f541)](https://www.soundtransit.org/ride-with-us/know-before-you-go/how-to-ride) 

###  [Ride the 2 Line to Marymoor Village and Downtown Redmond](https://www.soundtransit.org/ride-with-us/know-before-you-go/how-to-ride) 

 Posted on: March 17, 2025  [![Teen Programs Moving from Old Fire House](images/2a452c56ad3ae5b36caf81f8d38f7b4a98f262c199e06593325fedcd94bd896a)](https://www.redmond.gov/2262/Teen-Services?utm_medium=email&utm_source=govdelivery) 

###  [Teen Programs Moving from Old Fire House](https://www.redmond.gov/2262/Teen-Services?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 17, 2025  [![Learn How Mayor Birney is Advancing Solutions for Housing Supply Challenges](images/0acb74ae7a006517cbb30eba14458581955c076965656625bbd5ae1942db95c5)](https://www.redmond.gov/CivicAlerts.aspx?AID=2442&utm_medium=email&utm_source=govdelivery) 

###  [Learn How Mayor Birney is Advancing Solutions for Housing Supply Challenges](https://www.redmond.gov/CivicAlerts.aspx?AID=2442&utm_medium=email&utm_source=govdelivery) 

 Posted on: March 17, 2025  [![Learn How Redmonds Spaces and Buildings Will be Redesigned](images/e69a0a820be99f2dc027ccff1df0042cf46facdcf31c79907cfdd3e51bcdb5b4)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Learn How Redmond's Spaces and Buildings Will be Redesigned](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: March 17, 2025 | Last Modified on: March 17, 2025  [![Drones as First Responders Program Reached New Heights](images/cc0ef9d764ca76a3b4bfcabc4d21dbd81aaa04f6203f9e1e2d017c16f883288b)](https://www.redmond.gov/2161/Drone-Program) 

###  [Drones as First Responders Program Reached New Heights in 2024](https://www.redmond.gov/2161/Drone-Program) 

 Posted on: March 17, 2025  [![Summer Camp Registration News Flash](images/f5020135eb70d114960cc0eab7fa92c5894d91a690d36921da8db318c02427a2)](https://app.amilia.com/store/en/city-of-redmond/shop/programs/112728) 

###  [Register for Summer Activities](https://app.amilia.com/store/en/city-of-redmond/shop/programs/112728) 

 Posted on: March 11, 2025  [![Here in Redmond March News Flash](images/735b43c918e11bc78ceb4afa07cd56b4f9908dee321867d6000058ef4b581527)](https://www.youtube.com/watch?v=Li_Y0KSUHVY) 

###  [Helping Put Food on the Table for Those in Need](https://www.youtube.com/watch?v=Li_Y0KSUHVY) 

 Posted on: March 10, 2025  [![Get Involved with Derby Days News Flash](images/3f613d0550420172227bcc53243bd370cd4f25d393fb068ad36da109a870a0cd)](https://www.redmond.gov/1174/Get-Involved) 

###  [Get Involved with Derby Days](https://www.redmond.gov/1174/Get-Involved) 

 Posted on: March 10, 2025  [![Beat the Bunny News Flash](images/1cd11f48188bca2355c0d41d7090da7a8b35a983d7f306cb43c8d4e9964ff108)](https://app.amilia.com/store/en/city-of-redmond/shop/programs/108545?subCategoryIds=5610392) 

###  [Register Today for the Beat the Bunny Race](https://app.amilia.com/store/en/city-of-redmond/shop/programs/108545?subCategoryIds=5610392) 

 Posted on: March 10, 2025 | Last Modified on: March 10, 2025  [![Safer Streets Speed Cameras News Flash](images/81c412b5097687a522c88207a6cf5ad10928c1c473945a24aaf9d6f87075cf09)](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks) 

###  [Help Keep Our Streets Safe](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks) 

 Posted on: March 10, 2025  [![CNN News Flash](images/f48274b56fe59fa29be712c9782417d71364a7aaeb3c92d3f460fea35f8c03d0)](https://www.youtube.com/@CityofRedmond) 

###  [Watch City News Now](https://www.youtube.com/@CityofRedmond) 

 Posted on: March 10, 2025  [![March Milestones News Flash](images/d2a4fdab6058692b4100cb35375772a120e1a812e347da30806c632ddca25cff)](https://www.redmond.gov/2258/Recognition-Months-Weeks-and-Days?utm_medium=email&utm_source=govdelivery#march) 

###  [Celebrate March Milestones](https://www.redmond.gov/2258/Recognition-Months-Weeks-and-Days?utm_medium=email&utm_source=govdelivery#march) 

 Posted on: March 3, 2025  [![CNN News Flash](images/7ff3bd68e85e2a58d6fe9e63226512b103547df699ffc7ae1bf531c8f653f112)](https://www.facebook.com/CityOfRedmond?utm_medium=email&utm_source=govdelivery) 

###  [Introducing City News Now](https://www.facebook.com/CityOfRedmond?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025  [![Safer Streets Speed Cameras News Flash](images/cd3374bc877c96473ef1910d48da776387d6db414f35721d410a9eebc9776b46)](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks?utm_medium=email&utm_source=govdelivery) 

###  [Help Keep Our Streets Safe](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025  [![Storm Drain News Flash](images/07f1e67b6d55cb0c08f79ac02ce17bbfd91cfd0f3375daebf16cd9b530e69f67)](https://www.redmond.gov/410/NPDES-Stormwater-Permit?utm_medium=email&utm_source=govdelivery#IDDE) 

###  [Take Action to Curb Pollution](https://www.redmond.gov/410/NPDES-Stormwater-Permit?utm_medium=email&utm_source=govdelivery#IDDE) 

 Posted on: March 3, 2025  [![Heat Pumps News Flash](images/03555e7f904cb21789ad80a6c044e5bb7a03c720d3f8294266b6ab3d20a12081)](https://events.gcc.teams.microsoft.com/event/23d3b9a2-fedc-4492-a88c-c23c5a52fc08@222d2edd-8255-45bd-8597-52141b82f713?utm_medium=email&utm_source=govdelivery) 

###  [Learn How You Can Get a Heat Pump in a Qualified Adult Family Home](https://events.gcc.teams.microsoft.com/event/23d3b9a2-fedc-4492-a88c-c23c5a52fc08@222d2edd-8255-45bd-8597-52141b82f713?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025 | Last Modified on: March 3, 2025  [![Learn How the City is Planning for Safer Streets News Flash](images/690dd1c3cf17af6e0927b1113f5ef38a6cc0b3006e680761f30aca73bafdeebf)](https://www.redmond.gov/1152/Safer-Streets-Redmond) 

###  [Learn How the City is Planning for Safer Streets](https://www.redmond.gov/1152/Safer-Streets-Redmond) 

 Posted on: February 24, 2025  [![Take Action to Curb Pollution News Flash](images/28b60948b906937ff70ce39e5f8fae7d23d472cb8309e7aa4962da08fbfb6fc9)](https://www.facebook.com/watch/?v=600264416229252&rdid=yF86qTeW5zcDcovk) 

###  [Meet Our New Electric Fire Engine](https://www.facebook.com/watch/?v=600264416229252&rdid=yF86qTeW5zcDcovk) 

 Posted on: February 24, 2025  [![Get Help With Your Taxes News Flash](images/c3603ea05ca0decc50dc6831d7bccf90b97ac3299057ffc12f8b9ac45d085a96)](https://www.uwkc.org/need-help/tax-help/?utm_medium=email&utm_source=govdelivery) 

###  [Get Help With Your Taxes](https://www.uwkc.org/need-help/tax-help/?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 24, 2025 | Last Modified on: February 24, 2025  [![How Redmond Planned for Light Rail News Flash](images/fd189c0e7acb85d642b00d58e847bed3259cbccc18ead2e06813972c1e15ef33)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Learn How Redmond Planned for Light Rail](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: February 18, 2025  [![Review the Stormwater Management Plan News Flash](images/15b0fadb294088ed3da9fc51d722a756ddb15d79f37a76231de7534e9eba259d)](https://www.redmond.gov/410/NPDES-Stormwater-Permit) 

###  [Review the Stormwater Management Plan](https://www.redmond.gov/410/NPDES-Stormwater-Permit) 

 Posted on: February 18, 2025  [![Apply to the next Startup425 Accelerator News Flash](images/56c0ec878deea319224b7dcd0c0e7228e3e66dd313a771735804ce30ae2e2e62)](https://www.startup425.org/accelerator) 

###  [Apply to the Next Startup425 Accelerator](https://www.startup425.org/accelerator) 

 Posted on: February 18, 2025  [![Ways to Beat the Winter Blues News Flash](images/5911b2d82b2aefe4df8895acdbda2b5c46fef4e5a1b95f1a4d23e398969d80db)](https://www.youtube.com/watch?v=t2-0ElDgPzc) 

###  [Ways to Beat the Winter Blues](https://www.youtube.com/watch?v=t2-0ElDgPzc) 

 Posted on: February 10, 2025  [![Bike Silver Star News Flash](images/a4fce467649ce530cea35ac79c0b6c6128892b0ebfbf42b5ac2a24d9bfcb3efe)](https://www.redmond.gov/CivicAlerts.aspx?AID=2382) 

###  [Redmond Recognized as a Silver-Level Bicycle Friendly Community](https://www.redmond.gov/CivicAlerts.aspx?AID=2382) 

 Posted on: February 10, 2025  [![Redmond 2050 TMP News Flash](images/457a7852338966a155bb5903564314de6d02eb4ef42b33d1a386255bf768bddd)](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire) 

###  [Learn How Redmond 2050 is Planning for Access to Centers and Light Rail](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire) 

 Posted on: February 10, 2025  ![Presidents Day News Flash](images/9636b784c2b67519a5de8bdbf762a20d5dcc791d0f94c234940461d5d4ab4852)  

###  [Observing Presidents Day](https://redmond.gov/CivicAlerts.aspx?AID=2399) 

 Posted on: February 10, 2025  [![Celebrate Black History Month News Flash](images/82e95ac9d1583866197cc6f433d54a3a0d2dd2345fc708c0859e28a05847bfc2)](https://asalh.org/black-history-themes/?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Black History Month](https://asalh.org/black-history-themes/?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 3, 2025  [![New Electric Fire Truck Ushers in a New Era of Firefighting News Flash](images/9541d916476a78bac323764c4e165db636131f8a2eb964c7cb2c750a33601fef)](https://www.redmond.gov/CivicAlerts.aspx?AID=2390) 

###  [New Electric Fire Truck Ushers in a New Era of Firefighting](https://www.redmond.gov/CivicAlerts.aspx?AID=2390) 

 Posted on: February 3, 2025  [![Save the Date- Ride the Rails to Downtown Redmond in May News Flash](images/fc2c6ab21e7207c80151c107ede33a3fa60ac20ed200374a2b50722aefd7cb60)](https://www.soundtransit.org/get-to-know-us/news-events/news-releases/link-2-line-service-between-redmond-technology-station?utm_medium=email&utm_source=govdelivery) 

###  [Save the Date: Ride the Rails to Downtown Redmond in May](https://www.soundtransit.org/get-to-know-us/news-events/news-releases/link-2-line-service-between-redmond-technology-station?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 3, 2025  [![Prevent Damage to Your Pipes News Flash](images/80b38fc24f78dd425d890defc42f6fa092a8c0b1172c3eb25b73b142a07d7a50)](https://www.redmond.gov/397/WastewaterSewer?utm_medium=email&utm_source=govdelivery#FOG) 

###  [Prevent Damage to Your Pipes](https://www.redmond.gov/397/WastewaterSewer?utm_medium=email&utm_source=govdelivery#FOG) 

 Posted on: February 3, 2025  ![Council Conversations News Flash](images/a2a78e4b1aee1e1bd172df14e5477def182eb52c22c4f24f9391d43b808b5ef3)  

###  [Thank You for Joining Us at the Council Conversations – Town Hall](https://redmond.gov/CivicAlerts.aspx?AID=2387) 

 Posted on: January 27, 2025  [![How Do You Use Transit News Flash](images/3bf4fb46699db3681df0710335dfdc5c2c809604d92a8602526f13f568c46057)](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire?utm_medium=email&utm_source=govdelivery) 

###  [How Do You Use Transit?](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 27, 2025  [![Social Media News Flash](images/ae1665ba31efd5ed76326918784b0e7b26bd2f87c577669a4d9c4432101b334e)](https://www.facebook.com/CityOfRedmond) 

###  [Follow Us on Social Media](https://www.facebook.com/CityOfRedmond) 

 Posted on: January 27, 2025  [![Welcoming Community News Flash](images/88da9d8bb8ba7ad6dcf9f127050e0562ac74c3ea2c58db74a091eff9fce4946c)](https://www.redmond.gov/2241/Immigration-Resources?utm_medium=email&utm_source=govdelivery) 

###  [Affirming Our Commitment to a Welcoming Community](https://www.redmond.gov/2241/Immigration-Resources?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  ![Learn How Fire Staffing Models Are Enhanced News Flash](images/a87e30755583c2b725cfec27c746a7dc22d528d00ee70d8ad75d0935be929648)  

###  [Learn How Fire Department Staffing Models Are Enhanced](https://redmond.gov/CivicAlerts.aspx?AID=2374) 

 Posted on: January 21, 2025  [![Redmond 2050 Prepares Our City for Climate Change and Extreme Weather News Flash](images/abc71b22d43c6a7781e5aa0ce0d713b55c876d618ed0781478adec93342fd2a9)](https://www.redmond.gov/DocumentCenter/View/35171/05---Climate-Resilience-and-Sustainability-Element---draft-50-PDF?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Prepares Our City for Climate Change and Extreme Weather](https://www.redmond.gov/DocumentCenter/View/35171/05---Climate-Resilience-and-Sustainability-Element---draft-50-PDF?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  [![Disaster Assistance New Flash](images/08914af922f4a297584e3fce54553149fe12613bc46b2574c5a594391cd3bff2)](https://kcemergency.com/2025/01/07/state-financial-assistance-available-to-those-severely-impacted-by-the-november-bomb-cyclone/?utm_medium=email&utm_source=govdelivery) 

###  [Apply for Disaster Assistance: Governor's Proclamation Provides Aid for Bomb Cyclone Victims](https://kcemergency.com/2025/01/07/state-financial-assistance-available-to-those-severely-impacted-by-the-november-bomb-cyclone/?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  [![1-13 HIR News Flash](images/1ada4cee02dab1757f85f74c8d987b1100ddafb3d8d2a0a0216175b198df899c)](https://youtu.be/24dLNko-c4o?si=kzUD1-2k_1XcvNXw) 

###  [Here in Redmond: Take a Look Back at 2024](https://youtu.be/24dLNko-c4o?si=kzUD1-2k_1XcvNXw) 

 Posted on: January 13, 2025 | Last Modified on: January 13, 2025  [![1-13 MLK Day News Flash](images/02c5509e2191ccf093c8ed4ef13f8edf73b930aa2b556b67fdc87de0bbea2247)](https://www.redmond.gov/DocumentCenter/View/36085/Martin-Luther-King-Jr-Day-of-Service-Proclamation-12025?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Martin Luther King Jr.](https://www.redmond.gov/DocumentCenter/View/36085/Martin-Luther-King-Jr-Day-of-Service-Proclamation-12025?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 13, 2025  [![1-13 Firefighters Deployed News Flash](images/09709de83398363227ad55e1f30fc6dc3becc5549e3fbe438026aa7e32e171d9)](https://www.redmond.gov/CivicAlerts.aspx?AID=2366&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Fire Department Deployed Crew to Support California Wildfires](https://www.redmond.gov/CivicAlerts.aspx?AID=2366&utm_medium=email&utm_source=govdelivery) 

 Posted on: January 13, 2025  [![1-13 Redmond 2050 Outdoor Amenities News Flash](images/7b610a33ac0326d6d1055b94a475e37504f2d1e0373146fa6513837e4928cd6b)](https://www.redmond.gov/1609/Parks-Arts-and-Culture) 

###  [Learn How Redmond 2050 Creates More Access to Outdoor Amenities and Nature](https://www.redmond.gov/1609/Parks-Arts-and-Culture) 

 Posted on: January 13, 2025  [![Zoning News Flash](images/9c2efb4a49ca1ccec0a369e5c1b64cf5ad2c3bd52cdeb232fe991d608ed68512)](https://www.redmond.gov/2132/2024-Code-Updates?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Zoning and Other Regulatory Changes Effective January 1](https://www.redmond.gov/2132/2024-Code-Updates?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  ![Winter Weather News Flash](images/e991e1c15a671061694a611c40a63f654a6a9d3257d940ea338bffa064fa565a)  

###  [Be Prepared for Winter Weather](https://redmond.gov/CivicAlerts.aspx?AID=2362) 

 Posted on: January 6, 2025  [![Come Play with Us News Flash](images/a18a7b65ccf338efa0389a386ec66a6b0c76be16f00f6ca868ef8818b0398646)](https://app.amilia.com/store/en/city-of-redmond/shop/programs?utm_medium=email&utm_source=govdelivery) 

###  [Come Play With Us This Winter](https://app.amilia.com/store/en/city-of-redmond/shop/programs?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  [![Fitness News Flash](images/443f1ac5c994f24ed7cb1eaab6b84fb5fe715215becd4c6d1d679ff5df1203d6)](https://app.amilia.com/store/en/city-of-redmond/shop/memberships?) 

###  [Reach Your New Year Fitness Goals](https://app.amilia.com/store/en/city-of-redmond/shop/memberships?) 

 Posted on: January 6, 2025  [![Adopt-A-Drain News Flash](images/8db99f33cf9e21176ebbe365fcecaf2484ee42f78e2f216162f3582587ae0ab1)](https://wa.adopt-a-drain.org/?utm_medium=email&utm_source=govdelivery) 

###  [Make a Difference in Your Neighborhood](https://wa.adopt-a-drain.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  ![Share Your Photos News Flash](images/92b8a495b2428349f567ffe5390f80f6c35b898b1b04940974b7c84911c115a6)  

###  [Share Your Best Photos of 2024](https://redmond.gov/CivicAlerts.aspx?AID=2353) 

 Posted on: December 30, 2024  [![Storm Support News Flash](images/160214071b15ba98647430660caa5a7f343a11d2422b57439a5837a8a4afc7a9)](https://www.sba.gov/article/2024/12/23/sba-offers-disaster-assistance-washington-businesses-residents-affected-bomb-cyclone?utm_medium=email&utm_source=govdelivery) 

###  [Support Available for Residents and Businesses Impacted by the November Windstorm](https://www.sba.gov/article/2024/12/23/sba-offers-disaster-assistance-washington-businesses-residents-affected-bomb-cyclone?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024  [![Utilit Billing News Flash](images/524e986f6cfed6bba1d46eaf034527a274523ece60f4eb670ca3f96652e6ca0d)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024  [![ROW Fees News Flash](images/2f605ab7cb575c0f5b516669ca7cd805c472a6b320607118b4bdd9263746f3d1)](https://www.redmond.gov/372/Right-of-Way-Use-Permit?utm_medium=email&utm_source=govdelivery) 

###  [New Right of Way Use Fees Take Effect](https://www.redmond.gov/372/Right-of-Way-Use-Permit?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024 | Last Modified on: December 30, 2024  [![Lightrail News Flash](images/fed20b9c5a407bb4041e314f1eef911fb96c788f0e6bb5140b9c43cc9c3b3b1c)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#lightrail) 

###  [Light Rail is Coming to Downtown Redmond](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#lightrail) 

 Posted on: December 23, 2024  [![Budget News Flash](images/57b1a87b829dacdd4bedb526d15c800d9c66ae5aa63d1079d9e564c24fa2d083)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#budget) 

###  [Learn About Our New Budget](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#budget) 

 Posted on: December 23, 2024  [![Crows News Flash](images/1eb9c0f70544e7ba09ad947a1acba34cddac6cf02388e71c32ef02aa0e95dae0)](https://www.instagram.com/p/DDlRJVEvfdf/?utm_medium=email&utm_source=govdelivery) 

###  [Check Out How Many Crows Are Roosting in Redmond](https://www.instagram.com/p/DDlRJVEvfdf/?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 23, 2024  ![Card Fees News Flash](images/90f62d5e7779935b21dc949e4d2bd57170128f706aaece318b24e86dd543ad3c)  

###  [New Card Service Fees Begin on January 2](https://redmond.gov/CivicAlerts.aspx?AID=2345) 

 Posted on: December 23, 2024  [![Protect Your Pipes from Winter Weather News flash](images/f3567757bcb1bc94a8c8d129b7251a8fb1ee1e74365efcf90bfc0ed8a2a31da6)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#pipes) 

###  [Protect Your Pipes from Winter Weather](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#pipes) 

 Posted on: December 16, 2024  [![See How Redmond is Implementing Accessibility Improvements News Flash](images/c1efc8c1f8f72b65b9d7830239dabbf8d4e4ceadd1d59a74a2d559a6d59a7478)](https://www.redmond.gov/2057/31236/Inclusive-Design) 

###  [See How Redmond is Implementing Accessibility Improvements](https://www.redmond.gov/2057/31236/Inclusive-Design) 

 Posted on: December 16, 2024  [![Learn About New Right of Way Use Fees News Flash](images/aafaceff2f18cb2b3078ddc3b1a21d694362755f1c35b2ba9093f3f92004be57)](https://www.redmond.gov/2157/Right-of-Way-Use-Fee) 

###  [Learn About New Right of Way Use Fees](https://www.redmond.gov/2157/Right-of-Way-Use-Fee) 

 Posted on: December 16, 2024  [![Concrete Success News Flash](images/c3e58d1bee9e81e4d919fce037d6e399307a776da8230a68422ce039e8d5fcc8)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#concrete) 

###  [See Concrete Crew Success Stories](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#concrete) 

 Posted on: December 9, 2024  [![EV News Flash](images/0d6dadcb5cd7c9874fc7df87e6b24c072c6080baadb394c27480d44b5df23300)](https://www.letsconnectredmond.com/tmp/surveys/ev-charging?utm_medium=email&utm_source=govdelivery) 

###  [Share Your Thoughts on Electric Vehicles Infrastructure](https://www.letsconnectredmond.com/tmp/surveys/ev-charging?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024 | Last Modified on: December 9, 2024  [![Climate Heros News Flash](images/fba9895e24cb631377a9d2bdb2bbf56112389c22a6bbb4c46e2180c0b8579d99)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#parks) 

###  [See How Parks Are Leading the Charge as Climate Heroes](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#parks) 

 Posted on: December 9, 2024  [![Utility Billing News Flash](images/0cebb17fc7d7702b80d0cceaaaa1f61e787da383fb1c774477ebe8657748a181)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  [![Zoning Redmond 2050](images/7a201229799d39c5a9d8f08d02f05db4aa7797392109acd0c23b2dbbb15fcf1f)](https://www.redmond.gov/2226/Vesting-to-the-Redmond-Zoning-Code?utm_medium=email&utm_source=govdelivery) 

###  [Learn About the Two Editions of the Redmond Zoning Code](https://www.redmond.gov/2226/Vesting-to-the-Redmond-Zoning-Code?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  ![Card Fees News Flash](images/da26f122bac3ea7b0959f9ae2785ca322d5f2a554f817a9a5be05b73718b1375)  

###  [New Card Service Fees Begin January 2](https://redmond.gov/CivicAlerts.aspx?AID=2322) 

 Posted on: December 9, 2024  [![Energy Expense Help News Flash](images/84bb027c716195ac1a0d99ff72bfe40031d1c716ecd2ddd09b6e0b7180cabb97)](https://www.hopelink.org/programs/energy/?utm_medium=email&utm_source=govdelivery) 

###  [Receive Help with Energy Expenses](https://www.hopelink.org/programs/energy/?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  ![Redmond Lights News Flash](images/b398e657c7c3a30151d210cfa1d6cc6fef4f0f1b66be79ed3f94caa1cbf4a8af)  

###  [Join Us at Redmond Lights](https://redmond.gov/CivicAlerts.aspx?AID=2303) 

 Posted on: December 2, 2024  [![FOCUS News Flash](images/55200b40106c32d0cf1518c23b5511ad033096ce0f1a2cf629516b6c46a0d22c)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery) 

###  [Read the Latest Focus Newsletter](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 2, 2024  [![Be Prepared for Winter Weather NEws Flash](images/518eb108be810e299acedd590fb69a81057115ce2e453b96f8fad99d0990f717)](https://www.redmond.gov/1315/Weather-Alert-Updates?utm_medium=email&utm_source=govdelivery) 

###  [Be Prepared for Winter Weather](https://www.redmond.gov/1315/Weather-Alert-Updates?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 2, 2024  ![Meet Our New Snow Plows](images/461cb6d685da343ac0c811b5970c1214c6a8f81125ce7a00b268fdd5b4e183f0)  

###  [Meet Our New Snowplows](https://redmond.gov/CivicAlerts.aspx?AID=2300) 

 Posted on: December 2, 2024  ![Learn How Redmond 2050 Supports Local Businesses News Flash](images/8a8ebd5fdd7ab1bed6b1dffd63634f5f5e35791a65b29617a25b9bd2e0c73216)  

###  [Learn How Redmond 2050 Supports Local Businesses](https://redmond.gov/CivicAlerts.aspx?AID=2299) 

 Posted on: December 2, 2024  ![Construction News Flash](images/515493d14d96717775974ab790284ba408b711ddd17085b0853b7ace394b96c1)  

###  [Be Aware of Upcoming Construction](https://redmond.gov/CivicAlerts.aspx?AID=2297) 

 Posted on: December 2, 2024  [![Redmond Lights Newsflash](images/fb5634c362db982f835a1d9f0007c7d43e7bccc0a769de3e7030b9759da5afb9)](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Light and Art at Redmond Lights](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Shop Local News flash](images/c1ee4d2f0c648e9e625bc30c08915ca8125951c19fe75e710e5443e71f358fe3)](https://experienceredmond.com/Shop-Small/?utm_medium=email&utm_source=govdelivery) 

###  [Shop Local and Show Your Support](https://experienceredmond.com/Shop-Small/?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Comprehensive Plan News Flash](images/4600215501c242316ee5fb231602edfbce88979ddb08a89f09c6f37b6ae0d4b6)](https://www.redmond.gov/CivicAlerts.aspx?AID=2274&utm_medium=email&utm_source=govdelivery) 

###  [View the Adopted Redmond 2050 Plan](https://www.redmond.gov/CivicAlerts.aspx?AID=2274&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![EMS Fees News Flash](images/1efde78501ea1ad9fdd3e4a76d39e74385f52d7039b374ee97e048aef236cc83)](https://www.redmond.gov/faq.aspx?TID=106&utm_medium=email&utm_source=govdelivery) 

###  [Learn About EMS Transport Fees](https://www.redmond.gov/faq.aspx?TID=106&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  ![Happy Holidays News Flash](images/26d64e7ab318a3178bcd3279470f3148a515a71d63d4756efd3dd57ebd14563a)  

###  [Wishing You a Safe and Happy Holiday](https://redmond.gov/CivicAlerts.aspx?AID=2285) 

 Posted on: November 25, 2024  [![Help Others This Holiday News Flash](images/e7c1e1e480b5c1e65775e29dbe1f69b698821dc1c702a03a70d1e438de06b246)](https://www.redmond.gov/DocumentCenter/View/34804/Holiday-Giving-2024?utm_medium=email&utm_source=govdelivery) 

###  [Help Others During the Holidays](https://www.redmond.gov/DocumentCenter/View/34804/Holiday-Giving-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Universal Design News Flash](images/ab206aea4699f20780d58e82d2592f5c9287f3b455c4586042dbfc6802279020)](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond is Implementing Universal Design to Improve Accessibility and Inclusion](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  ![Card Fees News Flash](images/451449fc7c05f1413b7e248b71dc52a6112ba23163bdd118cd448dc84fb46f86)  

###  [New Card Service Fees Begin December 2](https://redmond.gov/CivicAlerts.aspx?AID=2266) 

 Posted on: November 18, 2024  [![TMP How you get around Redmond News Flash](images/3988dac278494a3fc7d217d8027c019e1df929434dba2ea47bd49d2dace22480)](https://www.letsconnectredmond.com/tmp?utm_medium=email&utm_source=govdelivery) 

###  [Share How You Get Around Redmond](https://www.letsconnectredmond.com/tmp?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  [![Stay Connected News Flash](images/f47f1664573094103675dd0438bbab9de2e3054c4b47b2b42cc08495e7d92e60)](https://www.redmond.gov/208/Enews-Subscription?utm_medium=email&utm_source=govdelivery) 

###  [Stay Connected on Sustainability, Parks, Growth, and More](https://www.redmond.gov/208/Enews-Subscription?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  [![New Small Business News Flash](images/852161ec6a533191e16b7811e810fcd73fd187f35c8ff7f8450ddd520fa07416)](https://www.youtube.com/watch?v=s-F3WBuCFWg) 

###  [Check out Redmond’s Stylish New Small Business](https://www.youtube.com/watch?v=s-F3WBuCFWg) 

 Posted on: November 12, 2024  [![Firefighters Return News Flash](images/5f3b5dc9d0d60af56120b9e4fc9c0f311ebb3a8bdf6b27b85d0ba2a3c0821304)](https://www.redmond.gov/CivicAlerts.aspx?AID=2255&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Firefighters Return from Hurricane Deployments](https://www.redmond.gov/CivicAlerts.aspx?AID=2255&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![Salary Commission News Flash](images/edae5cba63c01f7fec858fe9ce98478f7c470111f061a541c68b494eee117f5d)](https://www.redmond.gov/1972/Salary-Commission?utm_medium=email&utm_source=govdelivery) 

###  [Salary Commission Completes its Work](https://www.redmond.gov/1972/Salary-Commission?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![Utility Billing News Flash](images/3de945dbc671a91a0ddf0d0b38f338532728cdbfdd034aafa1031f1b2e4d26a8)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![King County Alert News Flash](images/791733122b5d163750f0422d471bfc9acafd5039aebacd60568c734d119e6249)](https://kingcounty.gov/en/dept/executive-services/health-safety/safety-injury-prevention/emergency-preparedness/alert-king-county?utm_medium=email&utm_source=govdelivery) 

###  [Sign Up for Emergency Alerts](https://kingcounty.gov/en/dept/executive-services/health-safety/safety-injury-prevention/emergency-preparedness/alert-king-county?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  [![Native American Heritage News Flash](images/d93d16cc27354e95cf915159853ba1d28b4b80ea42ab94d116b3d8c00ff1e64c)](https://www.nativeamericanheritagemonth.gov/?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Native American Heritage Month](https://www.nativeamericanheritagemonth.gov/?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  [![Redmond 2050 News Flash](images/3452ea6ac357b8230b9642720d7f46aaed846e3cfda25cac2fb2d394053ae323)](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Focuses on Equity and Inclusion](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  ![Credit Card Fees News Flash](images/411e93e441ddff7d6f6225d537c516e15037cb4fc2bd88fbd299f1c21b1fe5f2)  

###  [New Card Service Fees Begin December 2](https://redmond.gov/CivicAlerts.aspx?AID=2249) 

 Posted on: November 4, 2024  ![Small Business Workshop News Flash](images/4674df1ba88330c229535aa1287b5850e83df1a6777304106b800dd5ba63ec60)  

###  [Find Upcoming Opportunities for Redmond Businesses and Job Seekers](https://redmond.gov/CivicAlerts.aspx?AID=2248) 

 Posted on: November 4, 2024  [![Learn About the Impact of 2117 on Redmond News Flash](images/357b4b5f1f8fd11d33ea3f7adcf3f3c9a285dbde370d2abeb851eaaab0cfe32a)](https://www.redmond.gov/CivicAlerts.aspx?AID=2164&utm_medium=email&utm_source=govdelivery) 

###  [Learn About the Impact of 2117 on Redmond](https://www.redmond.gov/CivicAlerts.aspx?AID=2164&utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![See Environmental Sustainability Progress News Flash](images/aea2b059285695da428cdaff781e232b111a79e4ca3aa051563d0727111ea501)](https://www.redmond.gov/2182/2023-Environmental-Sustainability-Annual?utm_medium=email&utm_source=govdelivery) 

###  [See Environmental Sustainability Progress](https://www.redmond.gov/2182/2023-Environmental-Sustainability-Annual?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![Learn How Redmond Zones are Changing News Flash](images/d98b148527891b58c293899eed40643be6d656a0811c90fa5ee148c49e08839f)](https://www.redmond.gov/2108/Mixed-use-zones?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond Zones are Changing](https://www.redmond.gov/2108/Mixed-use-zones?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![No Lead in Redmonds Service Lines Newsflash](images/c49d5afa258dd0552778a9dc74105b89d3a7873cbe62810030b9519543785d2a)](https://www.redmond.gov/233/DrinkingWater?utm_medium=email&utm_source=govdelivery#lead) 

###  [No Lead in Redmond’s Service Lines](https://www.redmond.gov/233/DrinkingWater?utm_medium=email&utm_source=govdelivery#lead) 

 Posted on: October 28, 2024  ![Fall Back and Change Your Batteries News Flash](images/faab54db3b066f1c1b488b6089b4887f94bbbdecc5d07194ca92b95db0b822e7)  

###  [Fall Back and Change Your Batteries](https://redmond.gov/CivicAlerts.aspx?AID=2241) 

 Posted on: October 28, 2024  ![Jessica Forsythe News Flash](images/fe93c2ed0c0488f15d40aa788839dde7007d267813204270697dc396874d88a6)  

###  [City Council Vice President Jessica Forsythe Named Co-Chair of Eastrail](https://redmond.gov/CivicAlerts.aspx?AID=2238) 

 Posted on: October 21, 2024  [![Redmond 2050 Zoning News Flash](images/a98a8ac298c182fd99089d77d5f5f86d18f7a9eb7108adedc68d3e08354ca83d)](https://www.redmond.gov/1606/Housing?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Will Change Zoning in the City](https://www.redmond.gov/1606/Housing?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 21, 2024  [![Heats Pumps this Winter News Flash](images/70cce7b6be11548d0ee58d86f9a72eb13bd189aa1cbbfb9deb82b12b37781fac)](https://www.youtube.com/watch?v=U1bnOUMvrd8) 

###  [Stay Warm and Cozy with a Heat Pump](https://www.youtube.com/watch?v=U1bnOUMvrd8) 

 Posted on: October 21, 2024  ![Storm Drains News Flash](images/8426b45a8b4b1f112f84316a87e63153f0debd6fdde93ef3247fb8ec5feabcbe)  

###  [Make a Difference in Your Neighborhood](https://redmond.gov/CivicAlerts.aspx?AID=2233) 

 Posted on: October 21, 2024  [![Best Pizza in Redmond News Flash](images/960f41addcf252686caaa779073e75386d8c980c9834ec075cf3308e59f5aefe)](https://www.youtube.com/watch?si=1cVJfAsopp2Ldksm&utm_medium=email&utm_source=govdelivery&v=A-pVY__DWi0&feature=youtu.be) 

###  [Learn Where to Find the Best Pizza in Redmond](https://www.youtube.com/watch?si=1cVJfAsopp2Ldksm&utm_medium=email&utm_source=govdelivery&v=A-pVY__DWi0&feature=youtu.be) 

 Posted on: October 14, 2024  ![Honoring Indigenous Peoples Day News Flash](images/110b0e5ff688a81bf196a32e8c8f1c54dccac5934621b66a988e2d971dfa85d1)  

###  [Honoring Indigenous Peoples Day](https://redmond.gov/CivicAlerts.aspx?AID=2230) 

 Posted on: October 14, 2024  [![Drop Take Cover News Flash](images/e3a57af37fd712c7f2c6a0c3246c2596a55f163989e58b883738d64c2d2e6c5c)](https://www.youtube.com/playlist?list=PLs1gMujRSBY2t7JB4VS-AymFwN-6Lvg20) 

###  [Drop. Take Cover. Hold On.](https://www.youtube.com/playlist?list=PLs1gMujRSBY2t7JB4VS-AymFwN-6Lvg20) 

 Posted on: October 14, 2024  [![Read Local Eat Local News Flash](images/74a64e06cbea3cc920ae3af6eaff961c546b4a4b016081f5a09026497689d119)](https://www.redmond.gov/2142/Read-Local-Eat-Local?utm_medium=email&utm_source=govdelivery) 

###  [Read Local Eat Local](https://www.redmond.gov/2142/Read-Local-Eat-Local?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Redmond Lights News Flash](images/eb9c5193afd6da898a30c00c0ccf96da0d80b2f1e87ecbd272a57c9a0894c09a)](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

###  [Get Ready to Glow](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  ![Budget News Flash](images/5b74f19bd74957b33cd942ad9af3396d0ba3f02745dd3c234c9c6ddd8847dd04)  

###  [Read the City’s Preliminary Budget](https://redmond.gov/CivicAlerts.aspx?AID=2217) 

 Posted on: October 7, 2024  [![Heat Pumps News Flash](images/532c8a49e046ff745e844f002e0f9db7d76f5f73bfd55426184e508e18dba2cb)](https://www.redmond.gov/CivicAlerts.aspx?AID=2164) 

###  [Learn About the Impact of Initiative 2117 on Redmond](https://www.redmond.gov/CivicAlerts.aspx?AID=2164) 

 Posted on: October 7, 2024  [![Vent to Prevent News Flash](images/68f56a290a9b4ff434368da77f2c20bc41a9002c96e797faaaf5128427c649d9)](https://www.nfpa.org/education-and-research/home-fire-safety/smoke-alarms?utm_medium=email&utm_source=govdelivery) 

###  [Vent to Prevent](https://www.nfpa.org/education-and-research/home-fire-safety/smoke-alarms?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Cyber Security News Flash](images/0194c50666482909921de6895be5bec08adbac8b3dcaacde44e649dcf80dcc98)](https://www.cisa.gov/cybersecurity-awareness-month?utm_medium=email&utm_source=govdelivery) 

###  [Stay Cyber Safe](https://www.cisa.gov/cybersecurity-awareness-month?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Fall Traffic Counts News Flash](images/bf98c7d77ae6bb420ae78112ffd7063f210d5106141b4de3031cba2413738b12)](https://www.redmond.gov/863/Traffic-Counts) 

###  [Learn About Redmond’s Fall Traffic Counts](https://www.redmond.gov/863/Traffic-Counts) 

 Posted on: September 30, 2024  [![Sign Up for Silver Sneakers](images/31f3a461ee9f736ce68c971d1b9fc12c71545b2a16a8fb782af21dd6561ed5a1)](https://app.amilia.com/store/en/city-of-redmond/shop/memberships/52900) 

###  [Participate in SilverSneakers](https://app.amilia.com/store/en/city-of-redmond/shop/memberships/52900) 

 Posted on: September 30, 2024  [![Redmond 2050 News Flash](images/12adeb65daaaa4e73240a9aee24e8348876bd61dbf028ce584766a25bc2a77e1)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Redmond 2050: What’s Changing in Your Neighborhood](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: September 30, 2024  [![Redmond Senior & Community Center Passes News Flash](images/7dfb5edfd2049aa53e1899f1c2190add5ff623eddae03fcc362c5dfe5e60939b)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b7148f) 

###  [Learn About Our Redmond Senior & Community Center Passes](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b7148f) 

 Posted on: September 23, 2024  [![Redmond 2050 News Flash](images/30a51d07856687a6c6cd432883e463d04821ad89f3a327bfc3d7e41d83373da2)](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

###  [Redmond 2050: What is a Complete Neighborhood?](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

 Posted on: September 23, 2024  [![Homelessness News Flash](images/4b8287ef597b6bcb01c9fb10c220b2fd109695670ae3c75f611c32e7bdd3cfdf)](https://www.youtube.com/watch?v=w_SgXf3a5G8) 

###  [Be Part of the Solution to Homelessness](https://www.youtube.com/watch?v=w_SgXf3a5G8) 

 Posted on: September 23, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b69195) 

###  [Downtown Redmond Art Walk, Council Conversations, Redmond Lights, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b69195) 

 Posted on: September 18, 2024  [![Bike Survey](images/33f8bb0107e29efbd35df12d059d5cbc636a62117c4e88800af934892168b9f0)](https://www.surveymonkey.com/r/BFC_2024?utm_medium=email&utm_source=govdelivery) 

###  [Take Part in Our Bike Friendly Communities Survey](https://www.surveymonkey.com/r/BFC_2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: September 16, 2024  [![Utility BillingNews Flash](images/430586553e2d04fd1cb77891418ec86e1e2cb7583444e2d1c6907a03bfa1fa81)](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

###  [Learn About Changes to Utility Billing](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

 Posted on: September 16, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b4f2e9) 

###  [Fall Activities on the Farm, Council Conversations, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b4f2e9) 

 Posted on: September 11, 2024  [![Here in Redmond Home Newsflash](images/e705f6ee4181ad5ad8209563ae3dcde9e07ee2946487f071147feffd81406c2e)](https://www.youtube.com/watch?v=Xd09oa44rDI) 

###  [A Sense of Home is Meaningful for Everyone](https://www.youtube.com/watch?v=Xd09oa44rDI) 

 Posted on: September 9, 2024  ![Remembering September 11 Newsflash](images/5b37e47feee84005af1589ffacbe6ed5a01b6fb1ffc079c7509606615d39e2b0)  

###  [Remembering September 11](https://redmond.gov/CivicAlerts.aspx?AID=2172) 

 Posted on: September 9, 2024 | Last Modified on: September 9, 2024  ![Hispanic Heritage Month Newsflash](images/8510b0b85bd467cddf754ab0bfe24aec86cae3f724c2d1e6703bfcc45898b5ee)  

###  [Celebrate Hispanic Heritage Month](https://redmond.gov/CivicAlerts.aspx?AID=2170) 

 Posted on: September 9, 2024  [![Startup 425 Newsflash](images/1552f6f9073e582837db7b7d7ef7fd87a674872899b534490c3e6f76a75bd0df)](https://www.startup425.org/accelerator) 

###  [Learn About the Startup 425 Accelerator](https://www.startup425.org/accelerator) 

 Posted on: September 9, 2024  [![Safe Driving News Flash](images/fcbab4842c1db71293392180863907377407ca5ce29b8487a878b4127840d57d)](https://www.goredmond.com/blog/august-25-2022-1108am/back-school-safety-tips) 

###  [Make Back-to-School Safe](https://www.goredmond.com/blog/august-25-2022-1108am/back-school-safety-tips) 

 Posted on: September 3, 2024  [![Salmon SEEson News Flash](images/1eafb5163b0d74a3dbbdc87b8484c9b548ddea5ea717bbbebf282fdcfbf92b1e)](https://experience.arcgis.com/experience/779f2239705a42fba71f198d958da479/?data_id=dataSource_2-Salmon_viewing_sites_8034%3A7) 

###  [Discover Salmon SEEson](https://experience.arcgis.com/experience/779f2239705a42fba71f198d958da479/?data_id=dataSource_2-Salmon_viewing_sites_8034%3A7) 

 Posted on: September 3, 2024  [![Ready Plan News Flash](images/391226a0a2e027a3706b28ced43fd74c9b4ef857bcb8fadfd210c97d05007d0c)](https://www.ready.gov/plan) 

###  [Take Control of Your Readiness](https://www.ready.gov/plan) 

 Posted on: September 3, 2024  [![Redmond 2050 News Flash](images/60298fa6fca5409abecf38f771f6e689278930e0c8071673741b14110efe8355)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Nearing Completion: Learn the Latest About Redmond 2050](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: August 26, 2024  [![RSCC Membership News Flash](images/d7886ce8c5fd16c88125daaa7b413200ca821a80ad848e9c092d9e244ff2e2fa)](https://www.redmond.gov/2127/Hours-and-Operations) 

###  [Get a Membership to the Redmond Senior & Community Center](https://www.redmond.gov/2127/Hours-and-Operations) 

 Posted on: August 26, 2024  ![Safe Community News Flash](images/41c3d883a4831411b0b795af0b5e325a49deb6262ab61aab83ffe11fc3d8f1b8)  

###  [Help Keep Our Community Safe](https://redmond.gov/CivicAlerts.aspx?AID=2154) 

 Posted on: August 26, 2024  [![Climate Mayors Electric Vehicle Commitment](images/955871cf4f35bc56cfc2c8e77dc4a3bae6391ec7755c5eb499edd583e91a33f8)](https://www.climatemayors.org) 

###  [Learn About Climate Mayors Electric Vehicle Commitment](https://www.climatemayors.org) 

 Posted on: August 19, 2024  [![Bike Survey News Flash](images/4e9a0baf9939874d5319fe4aef2948a3dcc9f821ef568ed6b92e21f2b9bf3b8e)](https://www.surveymonkey.com/r/BFC_2024) 

###  [Take Part in Our Bike Friendly Communities Survey](https://www.surveymonkey.com/r/BFC_2024) 

 Posted on: August 19, 2024  [![Utility Billing News Flash](images/631528918d0823ed65f98af7249be29d8366cd22eacd2032eba23752fcaf340e)](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

###  [Learn About Changes to Utility Billing](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

 Posted on: August 19, 2024  [![Car Care to Protect Our Water News Flash](images/28ed8d0e2705aa2d0f95f0ce88209c9b0fc11eeaca363477ba41a1d5171ab409)](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#car) 

###  [Care for Your Car to Protect Our Water](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#car) 

 Posted on: August 19, 2024  [![Poet Laureate Chin-in Chen News Flash](images/254fc4568531697503346f8f75aa3b7520ef7ef6a3ac67da837c6ad059753d40)](https://poets.org/academy-american-poets-2024-poet-laureate-fellows) 

###  [Learn About Our Poet Laureate’s National Recognition](https://poets.org/academy-american-poets-2024-poet-laureate-fellows) 

 Posted on: August 12, 2024  [![NE 40th Street Underpass News Flash](images/339265ad6be709d542741a44d55e05601bd22dffc1d8d7004c1e7f527a402d2f)](https://www.redmond.gov/1151/Light-Rail-Extension) 

###  [See the Newly Opened NE 40th Street Underpass](https://www.redmond.gov/1151/Light-Rail-Extension) 

 Posted on: August 12, 2024  ![NNO News Flash](images/a89abfe9de46a079c9cfaacd1de87057e0a8766a59735511b8bc570eb63909e7)  

###  [Thank You All for National Night Out](https://redmond.gov/CivicAlerts.aspx?AID=2137) 

 Posted on: August 12, 2024  [![8-12_Keep our Roads Safe_News Flash](images/c10c37ff5fd48f9ff6e9d3bc3229bf2ef1110770fae85d54c3e49fd39aab9acd)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#driver-pedestrian) 

###  [Keep our Roads Safe](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#driver-pedestrian) 

 Posted on: August 12, 2024  [![Use Water Wisely News Flash](images/ef84e2ebb2a9ec136479ebf114882d168867644fb38fc11425827e16ddd5490c)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#water) 

###  [Use Water Wisely](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#water) 

 Posted on: August 12, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3ad380c) 

###  [Find your perfect fall activities and more!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3ad380c) 

 Posted on: August 7, 2024  [![Here in Redmond News Flash](images/1ac03a8d68d77684ff1fe672902e18baffdbf36f79772bd381008c0294836fab)](https://www.youtube.com/watch?v=YgjjZc7ATVM) 

###  [Keep Loved Ones Safe with the Take Me Home Program](https://www.youtube.com/watch?v=YgjjZc7ATVM) 

 Posted on: August 5, 2024  [![Budget Questionnaire](images/436ebf26dc14296395f2a722c2040a22356468eae33f8792f7083a953aa56529)](https://www.letsconnectredmond.com/budget-2024) 

###  [Share Your Budget Priorities with Us](https://www.letsconnectredmond.com/budget-2024) 

 Posted on: August 5, 2024  [![Community Survey Results News Flash](images/b97a664c1574182c3914d39d621bc3b957dc1ae8621e167a99cece4af7193635)](https://www.redmond.gov/856/Community-Surveys) 

###  [View the Annual Community Survey Results](https://www.redmond.gov/856/Community-Surveys) 

 Posted on: August 5, 2024  [![Stormwater, Streams, and More News Flash](images/95c47ebb7c5886f33e0a5bc0827821bbef6f1ff7e2bbc378e2fb09489a1c7ef1)](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

###  [We Want to Hear from You about Stormwater, Streams, and More](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

 Posted on: August 5, 2024  [![Free Composting Services News Flash](images/8a618337278995dfbc5d2daaf9961a5374742156199534cb1abe996ccea2b911)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#composting) 

###  [Get Free Composting Services for Businesses](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#composting) 

 Posted on: August 5, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3abf78b) 

###  [Fall Activity Registration is Open, Redmond Lights, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3abf78b) 

 Posted on: July 31, 2024  [![SUN Bucks News Flash](images/16dec5f66cd1c738c5a1de4b8b64ff96ad2c2d8c74234b6e93073eea9d842e6a)](https://sunbucks.dshs.wa.gov/en) 

###  [Get Help for Summer Meals](https://sunbucks.dshs.wa.gov/en) 

 Posted on: July 29, 2024  [![ROW Feedback News Flash](images/93f1755b2cb8d1e5c355510962570e4c2b514c853b1492a035df5feda90d1c5d)](https://www.letsconnectredmond.com/row) 

###  [We Want Your Feedback](https://www.letsconnectredmond.com/row) 

 Posted on: July 29, 2024  [![Heat Pumps News Flash](images/90335cd91ba5354fc66166b4fcb9bbff4ec26db77e7223984e796763a1825856)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#heat-pumps) 

###  [Save Thousands on Heat Pumps](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#heat-pumps) 

 Posted on: July 29, 2024  [![Ride the Rails to Redmond News Flash](images/3575d2a9f3dbf972d5a34c06fc6e86fc7b499c52367cfd14a949b2d091b21d2c)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#ride-the-rails) 

###  [Ride the Rails to Redmond](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#ride-the-rails) 

 Posted on: July 29, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3aa8c0a) 

###  [Register for Fall Activities, Free Life Jackets, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3aa8c0a) 

 Posted on: July 24, 2024  [![Parks, Trails, and Rec News Flash](images/42d4c2308306f6baf2746b72cb7f584b141abbe130c2d501259b3bcd2873eaa3)](https://www.redmond.gov/CivicAlerts.aspx?AID=2094) 

###  [Join Our Parks, Trails, and Recreation Commission](https://www.redmond.gov/CivicAlerts.aspx?AID=2094) 

 Posted on: July 22, 2024  [![Salary Commission News Flash](images/fe4ca01cd584ae45859979758f4eea84566361305547228a9a98b5153f7fa8d9)](https://www.redmond.gov/1972/Salary-Commission) 

###  [Join the Salary Commission](https://www.redmond.gov/1972/Salary-Commission) 

 Posted on: July 22, 2024  [![Ecomonic Development News Flash](images/5908cb5377f51cffc66192f8a0f91e110371059ef67adde418403d17358736b2)](https://www.redmond.gov/322/Economic-Development) 

###  [View Redmond’s Economic Development Strategic Plan](https://www.redmond.gov/322/Economic-Development) 

 Posted on: July 22, 2024  [![Dog Pop Up News Flash](images/e5ca955bd8de6f35b28e6f21a476c578d51cae2982e680b9837ccd1520ad9dc2)](https://www.letsconnectredmond.com/dogpark) 

###  [Paws and Play in Redmond](https://www.letsconnectredmond.com/dogpark) 

 Posted on: July 22, 2024  [![Storm Water and Surface Water News Flash](images/81913f659ab8a2dc692c537c13571e69c3169d7450a0b740c1e786b45e5987c8)](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

###  [Share Your Feedback on Stormwater and Surface Water](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

 Posted on: July 22, 2024  [![Horatio Flowers FOCUS News Flash](images/5304da95a66116105bd11ab04d9347a31a6c88b81917bfa24fb3bf9a7c60e749)](https://www.redmond.gov/2158/Focus---Summer-2024#shining-light) 

###  [Update on the Lamp Posts Blooming in Overlake](https://www.redmond.gov/2158/Focus---Summer-2024#shining-light) 

 Posted on: July 22, 2024  [![Focus_Summer 2024_News Flash](images/5a77db0331806dc93f47c2f149ee3c9a48bb54375fa784a948f517a66aa7f4fb)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#summer-camps) 

###  [Spend Your Summer in Redmond](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#summer-camps) 

 Posted on: July 15, 2024  [![civil service commissioner_News Flash](images/cfaf4a77da5a3851ca8890ed4651ea22982fb81a53b4d2a4a003a25b81bd1f05)](https://www.redmond.gov/1164/Civil-Service-Commission) 

###  [Volunteer to Help Redmond Public Safety](https://www.redmond.gov/1164/Civil-Service-Commission) 

 Posted on: July 15, 2024  [![Michael Plymouth Crossing_News Flash](images/6cb1463a00567e0de6ff6676d2087de47b1eb25e317b6b5e6b2f46e75ea3d365)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#connections) 

###  [Read About How Housing Builds Connections](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#connections) 

 Posted on: July 15, 2024 | Last Modified on: July 15, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a90e60) 

###  [Rockin' on the River, Derby Days Feedback, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a90e60) 

 Posted on: July 17, 2024  [![Parks and Rec Month News Flash](images/edfb8e90415910b9d9302981d66e49cd14732f6ef427f0d9c6bd1eb15bde6895)](https://www.redmond.gov/165/Parks-Recreation?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate National Parks and Recreation Month](https://www.redmond.gov/165/Parks-Recreation?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  [![Gardening Class News Flash](images/cfd9713f30677f66c0a4361f647d8b74484d7bb88ef566037786a97de40e1b1f)](https://cascadewater.org/water-efficiency/cascade-gardener/?utm_medium=email&utm_source=govdelivery) 

###  [Join Free Cascade Gardener Tours and Classes](https://cascadewater.org/water-efficiency/cascade-gardener/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  [![Don't Wait to Inflate](images/e4af51345c295debe1697e68ef63819ebd46719ac5477d76ce46711d18668609)](https://www.pugetsoundstartshere.org/DontwaittoInflate/?utm_medium=email&utm_source=govdelivery) 

###  [Don’t Wait to Inflate](https://www.pugetsoundstartshere.org/DontwaittoInflate/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  ![Focus_Summer 2024_News Flash](images/5a77db0331806dc93f47c2f149ee3c9a48bb54375fa784a948f517a66aa7f4fb)  

###  [Read the Latest Focus Newsletter](https://redmond.gov/CivicAlerts.aspx?AID=2076) 

 Posted on: July 3, 2024  [![Disability Pride Month](images/ffb6364ea3ff9f98a70a95c0df72891d7b12e771914f72d2516135e6b9b82bce)](https://thearc.org/blog/why-and-how-to-celebrate-disability-pride-month/?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Disability Pride Month](https://thearc.org/blog/why-and-how-to-celebrate-disability-pride-month/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 1, 2024  [![Right of Way Use Proposal](images/56899d532193f2429d83e305fde17e0ac726e892b193a3cd13598b76ab5e7384)](https://www.redmond.gov/2157/Proposed-Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Right-of-Way Use Fee Proposal](https://www.redmond.gov/2157/Proposed-Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 1, 2024  [![6-24 Take Me Home News Flash](images/2323a6292b68eba9b90015021d2ac4a48ddc1698adc3ea03ea4ecb67535c4cdb)](https://www.redmond.gov/2149/Take-Me-Home-Program?utm_medium=email&utm_source=govdelivery) 

###  [Register Your Loved One for Take Me Home](https://www.redmond.gov/2149/Take-Me-Home-Program?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Drink in Data Redmond Water News Flash](images/53352a61108e2d2b24142cc5f1d76fbe5df506100a8c047bea73a531fb343158)](https://www.redmond.gov/DocumentCenter/View/28402/2024-Water-Quality-Report?utm_medium=email&utm_source=govdelivery) 

###  [Drink in the Data for Redmond’s Water](https://www.redmond.gov/DocumentCenter/View/28402/2024-Water-Quality-Report?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Sewer Wastewater Plan News Flash](images/7e0fb561f4aa4fd66e8ce75d5f60fcade3d6cf5facd7b44a34a37f6f63c7ac9f)](https://www.letsconnectredmond.com/general-sewer-plan?utm_medium=email&utm_source=govdelivery) 

###  [Review the General Wastewater Plan](https://www.letsconnectredmond.com/general-sewer-plan?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Civil Council Commissioner News Flash](images/e0bd4746fce513f2e692c3110e470bfa73645630475cfb00be95c1c263422d79)](https://www.redmond.gov/CivicAlerts.aspx?AID=2034&utm_medium=email&utm_source=govdelivery) 

###  [Join the Civil Service Commission](https://www.redmond.gov/CivicAlerts.aspx?AID=2034&utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Right of Way Fee News Flash](images/63f730b9c96748a36767fe2df044ba7fe7aa9c0a653fea5935b65319eea4c920)](https://www.redmond.gov/2157/Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

###  [Learn About New Right of Way Use Fees](https://www.redmond.gov/2157/Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-17_Here in Redmond_News Flash](images/0b8d53e46f0e38bef02e720e1fa620bc0e1906c8176560742c8775d09baf8bbe)](https://www.youtube.com/watch?feature=youtu.be&utm_medium=email&utm_source=govdelivery&v=NvECG33vsak) 

###  [Relish in the Dog Days of Summer](https://www.youtube.com/watch?feature=youtu.be&utm_medium=email&utm_source=govdelivery&v=NvECG33vsak) 

 Posted on: June 17, 2024 | Last Modified on: June 17, 2024  [![6-17_Eastside Energy_News Flash](images/eed1ce7fcc5dcd5cc2f3fce5632e63c1ade1be1879190e895985994241c33520)](https://www.energysmarteastside.org/?utm_medium=email&utm_source=govdelivery) 

###  [Making a Difference on the Eastside Through a Clean Energy Program](https://www.energysmarteastside.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024  [![6-17_Tourism_News Flash](images/a9442264ade2202f5a4e8088241d943a4ce3b592a9acab863f2802e3c4180a46)](https://www.redmond.gov/DocumentCenter/View/32918/Redmond-Tourism-Strategic-Plan-FINAL-DRAFT?utm_medium=email&utm_source=govdelivery) 

###  [View Redmond’s First Tourism Strategic Plan](https://www.redmond.gov/DocumentCenter/View/32918/Redmond-Tourism-Strategic-Plan-FINAL-DRAFT?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024  [![6-17_Be Kind to Birds, Bats, Butterflies, and Bees_News Flash](images/daf9d63692317eeec6f5492b5b871197812f0b4cbb49ac259dae9039d23d91c8)](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg?utm_medium=email&utm_source=govdelivery) 

###  [Be Kind to Birds, Bats, Butterflies, and Bees](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024 | Last Modified on: June 17, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a243dc) 

###  [Derby Days Music, Summer Radness, Busker Program, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a243dc) 

 Posted on: June 12, 2024  [![6-10_enews_Pride_News Flash](images/123656141e2a312c44674e1723556a698bd6711543453e80ffc3eb53f292502f)](https://www.redmond.gov/DocumentCenter/View/32872/Pride-Proclamation-2024?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Pride Month](https://www.redmond.gov/DocumentCenter/View/32872/Pride-Proclamation-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![6-10_enews_OVerlake Passport Challenge_News Flash](images/fd724f3f8916128a38624a2dbf5b4e26c7549fb796c87fe16b1222d19b23bc5c)](https://experienceredmond.com/Overlake-Passport-Challenge/?utm_medium=email&utm_source=govdelivery) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport-Challenge/?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![6-10_enews_Marymoor Park_News Flash](images/b689b9a2a9819dacea605ff7021986c193bd78001a8e3a65a23d94e6d3290f7c)](https://survey123.arcgis.com/share/2ff9323500694fe494b4b8d1b79e3812?utm_medium=email&utm_source=govdelivery) 

###  [Help Improve Marymoor Park](https://survey123.arcgis.com/share/2ff9323500694fe494b4b8d1b79e3812?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![5-20_enews_EMS Week_News Flash](images/cf75020238d241c2dd9ef7f886d310400452a5b696ff0de687e9b0c934a019c1)](https://emsweek.org/?utm_medium=email&utm_source=govdelivery) 

###  [Join Us in Honoring Emergency Medical Services Week](https://emsweek.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Public Works Week_News Flash](images/ccccb5257d25e0799041410e98093f98615274d91690119e260ad5c0cedd93a6)](https://www.redmond.gov/1772/National-Public-Works-Week?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate National Public Works Week](https://www.redmond.gov/1772/National-Public-Works-Week?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Community Champions Award_News Flash](images/4d0fad5a19876ca71c15979a44a5e0e50a1686642ac108511a1f644ec8c83c09)](https://www.redmond.gov/CivicAlerts.aspx?AID=2007&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Earns Community Champion Award](https://www.redmond.gov/CivicAlerts.aspx?AID=2007&utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Startup and Small Business Meeting_News Flash](images/efc63beed1565180d9644eba880fdebd76fc58532d8db3a4f03d9202a39e1daa)](https://www.startup425.org/event-details/startup-small-business-coworking-redmond-may-2024?utm_medium=email&utm_source=govdelivery) 

###  [Attend a Startup and Small Business Coworking Event](https://redmond.gov/CivicAlerts.aspx?AID=2009) 

 Posted on: May 20, 2024  [![5-13_enews_RSCC Now Open_News Flash](images/525ff04aab5bdf6e7379f7c6be82ec80285a501787b252116871ddfe46284039)](https://www.youtube.com/watch?v=wSgFDsBoyB0) 

###  [Enjoy the New Redmond Senior & Community Center](https://redmond.gov/CivicAlerts.aspx?AID=2006) 

 Posted on: May 13, 2024  [![5-13_enews_AANHPI Month_News Flash](images/0b4f8e78245d89afa184ba6c352c8034cba653a10e3f313ece38d83026f0205d)](https://www.redmond.gov/DocumentCenter/View/32594/2024-AANHPI-Heritage-Month-Proclamation) 

###  [Celebrate Asian American, Native Hawaiian, and Pacific Islander Heritage Month](https://redmond.gov/CivicAlerts.aspx?AID=2005) 

 Posted on: May 13, 2024  ![5-13_enews_National Police Week_News Flash](images/f31b1a0c8a7f6f014b4e3fdfadb9a05ae5601c373780cc7d7d66356734eb3ffe)  

###  [Honoring National Police Week](https://redmond.gov/CivicAlerts.aspx?AID=2004) 

 Posted on: May 13, 2024  [![5-13_enews_Affordable Housing Week_News Flash](images/0bf274146bae70603198b133a0c642c5936dde210e9b3cc68d7af53b9ad08353)](https://www.housingconsortium.org/affordable-housing-week/?eType=EmailBlastContent&eId=40aade70-b1a0-46e5-9d6b-c9289a042db6) 

###  [Learn About Affordable Housing Week](https://redmond.gov/CivicAlerts.aspx?AID=2003) 

 Posted on: May 13, 2024  [![5-13_enews_Overlake Passport Challenge_News Flash](images/f6fb33fe20f4c2b522339ae00552c7e48caaacc33ded711959fe8102b02668a6)](https://experienceredmond.com/Overlake-Passport-Challenge) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport-Challenge) 

 Posted on: May 13, 2024  [![5-13_enews_Community Van_News Flash](images/85a904c1c36effe04e1e8962d97296ec4b5d10ab6bb09e8bbce8b41d26f5f8e9)](https://www.goredmond.com/redmond-community-van) 

###  [Take a Ride in a Community Van](https://www.goredmond.com/redmond-community-van) 

 Posted on: May 13, 2024  [![5-13_enews_Sustainable Vegetaion Management_News Flash](images/2cb19c1930d3e19e260eb097a5d306038de30bedb02baa08374b8ba3322d0a18)](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg) 

###  [Learn About the City’s Commitment to Environmental Stewardship](https://redmond.gov/CivicAlerts.aspx?AID=2000) 

 Posted on: May 13, 2024  [![5-6_enews_Older Americans Month_News Flash](images/cfc79dbc2a4bb4299f72175215d281402b12112bfd6deca961ce2fa7de0a9608)](https://www.redmond.gov/DocumentCenter/View/32591/Older-Americans-Month-Proclamation---May-2024?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Older Americans Month](https://www.redmond.gov/DocumentCenter/View/32591/Older-Americans-Month-Proclamation---May-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Bike Everywhere Day_News Flash](images/20eca8fddebdf17742d924b70212e945c0a802bededc5298a7d39523c86a392f)](https://cityofredmond.maps.arcgis.com/apps/instant/basic/index.html?47.667=&appid=659e8920e5de4bb3867c577a1a770c9e&center=-122.1201&hiddenLayers=18f0bf745dc-layer-20&level=12&utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Bike Everywhere Month](https://cityofredmond.maps.arcgis.com/apps/instant/basic/index.html?47.667=&appid=659e8920e5de4bb3867c577a1a770c9e&center=-122.1201&hiddenLayers=18f0bf745dc-layer-20&level=12&utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Walking Tour_News Flash](images/d31f6bd7493349b648634d144e617b692a09b41458491b0783e7a8c3859ac910)](https://www.letsconnectredmond.com/safe-streets-for-all?utm_medium=email&utm_source=govdelivery) 

###  [Help Make Roads Safer](https://redmond.gov/CivicAlerts.aspx?AID=1994) 

 Posted on: May 7, 2024  [![5-6_enews_Clean Drinking Water_News Flash](images/e485016f1b7bdf6cafd0e25c6c3dccb7fc028f738144600645f833d20956d032)](https://www.redmond.gov/1834/Drinking-Water-Operations?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Clean Drinking Water](https://www.redmond.gov/1834/Drinking-Water-Operations?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Clean Streams_News Flash](images/030be493289c7c19ddc4dda9fb0a7b6ea61dec3ba0229d42b58488330f2c3bbc)](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#neighborhood) 

###  [Keep Our Streams Clean](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#neighborhood) 

 Posted on: May 7, 2024  [![5-6_enews_Migratory Birds_News Flash](images/50f10e8b7ce191a6a4cb22f52482fc6ddba26566a10088f11304a34d7f5e82fd)](https://www.migratorybirdday.org/?utm_medium=email&utm_source=govdelivery) 

###  [Protect Insects to Protect Birds](https://www.migratorybirdday.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![4-29_enews_RSCC Grand Opening copy](images/b0372619533282f04a3cb34029f5c5b1341b79db52751a05d24f14fefc116453)](https://www.redmond.gov/1867/Redmond-Senior-Community-Center?utm_medium=email&utm_source=govdelivery) 

###  [Join Us for the Redmond Senior & Community Center Grand Opening](https://www.redmond.gov/1867/Redmond-Senior-Community-Center?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Municipal Campus Parking copy](images/e71334ea8c941f338218becbcb092dfac09c1f3c583244814ffc840565770dbb)](https://www.redmond.gov/2124?utm_medium=email&utm_source=govdelivery) 

###  [Stay Informed About Municipal Campus Parking Changes](https://www.redmond.gov/2124?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Overlake Passport copy](images/bc0f2381088247b5208b358157f7d33f3b56c4ccf92f2732df8d2d8b0503d091)](https://experienceredmond.com/Overlake-Passport Challenge/?utm_medium=email&utm_source=govdelivery) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport Challenge/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Light the Night Red copy](images/f059b720e779a14c2331854f869b79ba8c5658d3038740e7acd99d5942479fd0)](https://weekend.firehero.org/events/memorial-weekend/light-night-fallen-firefighters/?utm_medium=email&utm_source=govdelivery) 

###  [Light the Night to Honor Fallen Firefighters](https://weekend.firehero.org/events/memorial-weekend/light-night-fallen-firefighters/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Prepare for Wildfires copy](images/9223edc70b0287981fa95b312c39cf2bebef80121365539244f6401160961828)](https://www.nfpa.org/Events/Events/National-Wildfire-Community-Preparedness-Day?utm_medium=email&utm_source=govdelivery) 

###  [Keep Your Home Safe this Wildfire Season](https://www.nfpa.org/Events/Events/National-Wildfire-Community-Preparedness-Day?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Summer Planning Academy copy](images/986ce6719ca7286e0013eef2a1cfd8c577ef8fc93354939bbcea5f70edd1be25)](https://www.psrc.org/get-involved/summer-planning-academy?utm_medium=email&utm_source=govdelivery) 

###  [Apply for the Regional Summer Planning Academy](https://redmond.gov/CivicAlerts.aspx?AID=1952) 

 Posted on: April 29, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39877bd) 

###  [Grand Opening of the New Redmond Senior & Community Center, Art Walk Muralists, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39877bd) 

 Posted on: April 24, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/396fb66) 

###  [Earth Day with Green Redmond, Community Paint Day, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/396fb66) 

 Posted on: April 17, 2024  [![4-15_enews_Work Zone Awareness_News Flash](images/190fc0573878a4c42efd4a72d21bc840585c9e56514c896ab36a6d2b3d199dbc)](https://wsdot.wa.gov/travel/traffic-safety-methods/work-zone-safety?utm_medium=email&utm_source=govdelivery) 

###  [Slow Down for National Work Zone Awareness Week](https://wsdot.wa.gov/travel/traffic-safety-methods/work-zone-safety?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_RSCC Parking_News Flash](images/86659a8c8cb7554bafd8e0c9994f743a8fe01c6e6992dd232a44bf6a6670fe2f)](https://www.redmond.gov/2124/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Senior & Community Center and Municipal Campus Parking](https://www.redmond.gov/2124/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Do Gooder Scholarship_News Flash](images/6f307570a657806b9189fdeb9b50e0e687d0018fc85e8a6d22bfc048c021fd63)](https://www.redmond.gov/1412/Derby-Do-Gooder-Scholarship?utm_medium=email&utm_source=govdelivery) 

###  [Apply for Redmond’s Derby Days Do-Gooder Scholarship](https://www.redmond.gov/1412/Derby-Do-Gooder-Scholarship?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Demographics_News Flash](images/092e3f65b1eb4abf8b200418569afd963a28c342f4c3033cb7d9580a25ce3f9f)](https://www.redmond.gov/818/Demographics-and-Statistics?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Demographics](https://www.redmond.gov/818/Demographics-and-Statistics?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Zoning Updates_News Flash](images/5b2896143c384484b0d759e9864319e8431e7095eae4fd0172499d721dbc29d8)](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Our Community is Changing](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39555e4) 

###  [Be Part of Derby Days, Scholarship for High School Seniors, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39555e4) 

 Posted on: April 10, 2024  [![Parks & Rec eNews](images/dfb655189ee92beb560da5f4ff2988a17a3195406baa380bd0dc281b3617968d)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3942b8a) 

###  [Pop-up Dog Parks Opening, Earth Day Activities, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3942b8a) 

 Posted on: April 5, 2024  [![4-1_enews_Earth Month_News Flash](images/1c0aab85ff4ec3a75cc9a88aa5093e07c21ce2ab6016cfe379733a4c0089dd8f)](https://www.redmond.gov/1725/Earth-Month) 

###  [Celebrate Earth Month](https://www.redmond.gov/1725/Earth-Month) 

 Posted on: April 1, 2024  [![4-1_enews_Natural Yard Care_News Flash](images/c31ca3a9d408fe728c51068c06ff9edb024471a1ffe10c5ee6f749b062e16bee)](https://www.naturalyardcare.org/?utm_medium=email&utm_source=govdelivery) 

###  [Grow Healthy Natural Yards](https://www.naturalyardcare.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_RSCC Parking_News Flash](images/9fe3f24bc1cfd8c6977691c4f3caaab5cba529eb0d87d2350494a2d7d751d475)](https://www.redmond.gov/2124/32981/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Senior & Community Center and Municipal Campus Parking](https://www.redmond.gov/2124/32981/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Sexual Assault Awareness Month_News Flash](images/50d976a859bf53f668e157030ebb3a9b2a7706cf4bda6f620554b1e183fa8c4e)](https://www.redmond.gov/DocumentCenter/View/32202/Sexual-Assault-Awareness-Month-2024-Proclamation?utm_medium=email&utm_source=govdelivery) 

###  [Recognizing Sexual Assault Awareness Month](https://www.redmond.gov/DocumentCenter/View/32202/Sexual-Assault-Awareness-Month-2024-Proclamation?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Volunteer Month_News Flash](images/7c2a1426cfc502b63e02c4c38d9ed3d4347a491fc0ea9dc83ab99405100ec645)](https://www.redmond.gov/661/Volunteer-Opportunities?utm_medium=email&utm_source=govdelivery) 

###  [Participate in National Volunteer Month](https://www.redmond.gov/661/Volunteer-Opportunities?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Donate Blood_News Flash](images/b358aae07114696a1d120b1c48e75b18d5daec48c165e90503b168431bbe0dc6)](https://donate.bloodworksnw.org/donor/schedules/sponsor_code?utm_medium=email&utm_source=govdelivery) 

###  [Save a Life by Donating Blood](https://donate.bloodworksnw.org/donor/schedules/sponsor_code?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024 <script type="text/javascript" language="javascript"><!--function redrawContent(closeModal) {raiseAsyncPostback('ctl00_ctl00_MainContent_ModuleContent_ctl00_contentUpdatePanel', '', closeModal);}$(document).ready(function () {if (!window.isResponsiveEnabled) { $('div.moduleContentNew').addClass('minWidth320px');}var color = $("div.moduleContentNew").css("color") + " !important";var style = $('<style>span.arrow { color:' + color + '; }</style>');$('html > head').append(style);});function pageLoad() {$('#newsSortBy').bind('change', function () { var url = $(this).val(); if (url) { window.location = url; } return false;});}//--></script> <script type="text/javascript">order+='ModuleContent\n'</script> 

### Live Edit

 [](https://redmond.gov/CivicAlerts.aspx?AID=2239)  <script type="text/javascript">//<![CDATA[Sys.Application.add_init(function() { $create(AjaxControlToolkit.ModalPopupBehavior, {"BackgroundCssClass":"modalBackground","CancelControlID":"ctl00_LiveEditCloseButton","PopupControlID":"ctl00_ctl00_MainContent_ctl00_liveEditPopupWindow","PopupDragHandleControlID":"ctl00_liveEditTitleBar","dynamicServicePath":"/CivicAlerts.aspx","id":"editItemBehavior"}, null, null, $get("ctl00_ctl00_MainContent_ctl00_liveEditSpawnWindow"));});//]]></script> 

###  [Popular](https://redmond.gov/QuickLinks.aspx?CID=105) 

 1.  [Home](https://redmond.gov/CivicAlerts.aspx?AID=2239)  
 1.  [Events](https://redmond.gov/294)  
 1.  [Jobs](https://www.governmentjobs.com/careers/redmondwa)  
 1.  [Recreation Activities](https://redmond.gov/184/Activities)  
 /QuickLinks.aspx 

###  [Find](https://redmond.gov/QuickLinks.aspx?CID=106) 

 1.  [City Council](https://redmond.gov/189)  
 1.  [Parks & Trails](https://redmond.gov/186)  
 1.  [Permits](https://redmond.gov/898)  
 1.  [Transportation](https://redmond.gov/221)  
 /QuickLinks.aspx 

###  [Report / Request](https://redmond.gov/QuickLinks.aspx?CID=107) 

 1.  [Report an Issue](https://redmondwa.qscend.com/311)  
 1.  [Request a Service](https://redmondwa.qscend.com/311)  
 1.  [Public Record](https://redmond.gov/777)  
 1.  [Police Record](https://redmond.gov/698)  
 /QuickLinks.aspx 

###  [Helpful Links](https://redmond.gov/QuickLinks.aspx?CID=108) 

 1.  [ADA Program](https://redmond.gov/871)  
 1.  [Title VI](https://redmond.gov/857)  
 1.  [Website Accessibility](https://redmond.gov/873/5722/Web-Accessibility)  
 1.  [Website Policies](https://redmond.gov/385)  
 /QuickLinks.aspx 

### Social Media

  [Facebook](https://redmond.gov/facebook)   [X](https://redmond.gov/twitter)   [Instagram](https://redmond.gov/instagram)   [YouTube](https://redmond.gov/youtube)  

### Sign Up For Our Newsletter

 1. 
 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvca56cd53-4ad3-45f7-9522-a35eb6c948a8.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1.    

 ![Redmond Washington Homepage](images/e46b952d10bebc0723ee994672c2713de87095c3f785afbca674b1d952211e42)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvce94195d-0d21-4a69-9b41-22564e582b93.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1. Phone:  [425-556-2900](tel:425-556-2900) 

 1.  [15670 NE 85th Street](https://goo.gl/maps/CJcLDqJFWRpxZxbL6) 

 1. P.O. Box 97010

 1.  [Redmond, WA 98073-9710](https://goo.gl/maps/CJcLDqJFWRpxZxbL6) 
 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdv97860bf2-90f8-4398-876c-7ac5e8181ba3.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1.  [Contact Us](https://redmond.gov/directory)  

 1.  [Site Map](https://redmond.gov/sitemap)  

 1.  [Website Feedback](https://redmond.gov/FormCenter/Communications-12/Website-Feedback-87)  
 /QuickLinks.aspx Loading Loading Do Not Show AgainClose <script src="/Assets/Scripts/APIClient.js"></script><script src="/Assets/Mystique/Shared/Scripts/Moment/Moment.min.js"></script><script src="/Assets/Scripts/SplashModal/SplashModalRender.js"></script><script> $(document).ready(function () { var filter = { targetId: '', targetType: 0 } new SplashModalRender().triggerRender(filter); });</script><script src="/-1135462429.js" type="text/javascript"></script><script>document.addEventListener("DOMContentLoaded", () => { const getValueTS = (elem, attr) => { const val = window.getComputedStyle(elem)[attr]; return val? parseInt(val, 10) : undefined; }; const clampTS = (number, min, max) => Math.min(Math.max(number, min), max); const isPageEditingTS = () => { return document.querySelector("#doneEditing") !== null || typeof DesignCenter !== "undefined"; }; const isTransparentTS = (elem) => { const bg = window.getComputedStyle(elem)['background-color']; const bgColorRegexTS = /rgba\((\d+), (\d+), (\d+), (\d*\.?\d*)\)/; const matchState = bg.match(bgColorRegexTS); if (!matchState || matchState.length !== 5) return false; const alpha = parseFloat(matchState[4], 10); return alpha >= 0 && alpha < 1; }; const iterateLeftPads = (callback) => { const containersTS = document.querySelectorAll("[class^='siteWrap'],[class*=' siteWrap']"); containersTS.forEach(containerTS => { if (containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-leftpad') === null) { callback(containerTS); } }); }; const iterateRightPads = (callback) => { const containersTS = document.querySelectorAll("[class^='siteWrap'],[class*=' siteWrap']"); containersTS.forEach(containerTS => { if (containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-rightpad') === null) { callback(containerTS); } }); }; const anchor = document.getElementById("divToolbars"); const bodyWrapper = document.getElementById("bodyWrapper"); const outerSizingTS = document.getElementById("bannerContainerTS"); const innerSizingTS = document.getElementById("bannerSizingTS"); const bodyContainerTS = document.getElementById("bodyContainerTS"); const headerContainerTS = document.getElementById("headerContainerTS"); const fixedTopTS = document.querySelector(".fixedTopTS"); const fixedBottomTS = document.querySelector(".fixedBottomTS"); const fixedLeftTS = document.querySelector(".fixedLeftTS"); const fixedRightTS = document.querySelector(".fixedRightTS"); let initialTopTS; let topAttachTS; if (fixedTopTS) { initialTopTS = getValueTS(fixedTopTS, 'top'); const attachment = fixedTopTS.getAttribute('data-attach'); if (attachment) topAttachTS = document.getElementById(attachment); } const resizeAdjustmentTS = () => { const editing = isPageEditingTS(); const anchorStyle = getComputedStyle(anchor); const anchorPaddingTop = parseInt(anchorStyle.paddingTop, 10); // console.log("Padding Top:", anchorPaddingTop);  // Sticky Top Adjustment if (fixedTopTS) { if (editing) { fixedTopTS.classList.add("forceUnfixTS"); } else { fixedTopTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedTopTS).position === "sticky") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; fixedTopTS.style.top = `${anchorHeight + initialTopTS}px`; bodyWrapper.style.paddingTop = `${anchorHeight - anchorPaddingTop}px`; if (isTransparentTS(fixedTopTS)) { innerSizingTS.style.paddingTop = `${initialTopTS + fixedTopTS.offsetHeight - 1}px`; outerSizingTS.style.paddingTop = ""; } else { outerSizingTS.style.paddingTop = ""; innerSizingTS.style.paddingTop = ""; } } else { const mobileMenu = document.getElementById("nav-open-btn"); const mobileMenuHeight = mobileMenu? mobileMenu.offsetHeight : 0; fixedTopTS.style.top = ""; bodyWrapper.style.paddingTop = `${anchor.offsetHeight + mobileMenuHeight - anchorPaddingTop}px`; } } // Sticky Bottom Adjustment if (fixedBottomTS) { if (editing || fixedBottomTS.offsetHeight > 200) { fixedBottomTS.classList.add("forceUnfixTS"); } else { fixedBottomTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedBottomTS).position === "fixed") { bodyContainerTS.style.paddingBottom = `${fixedBottomTS.offsetHeight}px`; bodyWrapper.style.paddingTop = `${anchor.offsetHeight - anchorPaddingTop}px`; } else { bodyContainerTS.style.paddingBottom = ""; bodyWrapper.style.paddingTop = `${anchor.offsetHeight - anchorPaddingTop}px`; } } // Fixed Left Adjustment if (fixedLeftTS) { if (editing) { fixedLeftTS.classList.add("forceUnfixTS"); } else { fixedLeftTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedLeftTS).position === "fixed") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; const headerHeight = headerContainerTS.offsetHeight - 1; fixedLeftTS.style.top = `${anchorHeight + headerHeight + 100}px`; const leftBoundingTS = fixedLeftTS.getBoundingClientRect(); iterateLeftPads(containerTS => { const containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= leftBoundingTS.right) { containerTS.style.paddingLeft = `${leftBoundingTS.width + 16}px`; } }); } } // Fixed Right Adjustment if (fixedRightTS) { if (editing) { fixedRightTS.classList.add("forceUnfixTS"); } else { fixedRightTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedRightTS).position === "fixed") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; const headerHeight = headerContainerTS.offsetHeight - 1; fixedRightTS.style.top = `${anchorHeight + headerHeight + 100}px`; const rightBoundingTS = fixedRightTS.getBoundingClientRect(); iterateRightPads(containerTS => { const containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= rightBoundingTS.right) { containerTS.style.paddingRight = `${rightBoundingTS.width + 16}px`; } }); } } }; const scrollAdjustmentTS = () => { if (!fixedTopTS || !topAttachTS) return; const topPosition = getComputedStyle(fixedTopTS).position; if (topPosition === "sticky" || topPosition === "absolute") { const anchorBounding = anchor.getBoundingClientRect(); const attachBounding = topAttachTS.getBoundingClientRect(); fixedTopTS.style.top = `${Math.max(anchorBounding.bottom - 1, attachBounding.bottom)}px`; } else { fixedTopTS.style.top = `${initialTopTS}px`; } }; // Event Listeners for Scroll and Resize window.addEventListener("scroll", scrollAdjustmentTS); window.addEventListener("resize", () => { clearTimeout(this.adjustTimeout); this.adjustTimeout = setTimeout(resizeAdjustmentTS, 350); }); // Initial adjustment on page load resizeAdjustmentTS(); });</script><script>if (document.location.pathname == "/list.aspx") { const urlParams = new URLSearchParams(window.location.search); const theEmail = urlParams.get('email'); if (theEmail) { $("#emailAddressSignIn").val(theEmail); signIn(); }}</script><script>$(document).ready(function() { // Preload Images for Graphic Buttons.5 seconds after page loads var waitToPreload = 500; // Parse through the styles on the page, finding any image URLs $($("style").text().match(/url\s*\('?\/?(?:[^/]+\/)*?([^/:]+)'?\)/g)).each(function() { var url = this.replace("url(","").replace(")","").replaceAll("'","").replaceAll('"',""); setTimeout(preloadImage, waitToPreload, url); }); function preloadImage(url) { var image = $("<img />"); $(image).attr('src',url).appendTo('body').hide(); }});</script><script src="//cdn.loop11.com/embed.js" type="text/javascript" async="async"></script><script type="text/javascript">/*<![CDATA[*/(function() {var sz = document.createElement('script'); sz.type = 'text/javascript'; sz.async = true;sz.src = '//siteimproveanalytics.com/js/siteanalyze_6745.js';var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(sz, s);})();/*]]>*/</script><script type="text/javascript"> window._monsido = window._monsido || { token: "gUHJ1NzC3wpOQrmj03jgIg", statistics: { enabled: true, cookieLessTracking: false, documentTracking: { enabled: true, documentCls: "monsido_download", documentIgnoreCls: "monsido_ignore_download", documentExt: [], }, }, heatmap: { enabled: true, }, pageAssistV2: { enabled: true, theme: "light", mainColor: "#783CE2", textColor: "#ffffff", linkColor: "#783CE2", buttonHoverColor: "#783CE2", mainDarkColor: "#052942", textDarkColor: "#ffffff", linkColorDark: "#FFCF4B", buttonHoverDarkColor: "#FFCF4B", greeting: "Discover your personalization options", direction: "leftbottom", coordinates: "undefined undefined undefined undefined", iconShape: "circle", title: "Personalization Options", titleText: "Welcome to PageAssist™ toolbar! Adjust the options below to cater the website to your accessibility needs.", iconPictureUrl: "logo", logoPictureUrl: "", logoPictureBase64: "", languages: [""], defaultLanguage: "", skipTo: false, alwaysOnTop: false,hotkeyEnabled: false }, };</script><script type="text/javascript" async src="https://app-script.monsido.com/v2/monsido-script.js"></script><script> (function () { const minWidth = 220; const maxWidth = 500; // Facebook widget will not expand past 500 function clamp__TS(num, min, max) { return Math.min(Math.max(num, min), max); } function adjustFacebookContainers__TS() { const iframes = document.querySelectorAll('iframe[src*="facebook.com"]'); iframes.forEach(iframe => { if (!iframe.parentElement.classList.contains('facebook-container')) { const container = document.createElement('div'); container.classList.add('facebook-container'); iframe.parentNode.insertBefore(container, iframe); container.appendChild(iframe); } adjustContainer__TS(iframe.parentElement); }); } function adjustContainer__TS(container) { const frame = container.querySelector('iframe'); if (!frame) { console.warn("No facebook widget found..."); return; } const containerWidth = container.clientWidth; const newWidth = clamp__TS(containerWidth, minWidth, maxWidth); // Use jQuery to manipulate the iframe's src and dimensions const src = new URL(frame.getAttribute("src")); src.searchParams.set("width", newWidth); frame.setAttribute("src", src); frame.setAttribute("width", newWidth); } window.addEventListener('load', adjustFacebookContainers__TS); window.addEventListener('resize', adjustFacebookContainers__TS); })();</script><script> function moveBannerToOuterWrap() { if ($(".fixedBannerTS #bannerDivbanner2").length) { $(".fixedBannerTS #bannerDivbanner2").appendTo("#outer-wrap"); } else { setTimeout(function () { moveBannerToOuterWrap(); }, 500); } } moveBannerToOuterWrap();</script> <script> function googleTranslateElementInit() { new google.translate.TranslateElement({ pageLanguage: "en" }, "google_translate_element"); // begin accessibility compliance $('img.goog-te-gadget-icon').attr('alt','Google Translate'); $('div#goog-gt-tt div.logo img').attr('alt','translate'); $('div#goog-gt-tt.original-text').css('text-align','left'); $('.goog-te-gadget-simple.goog-te-menu-value span').css('color','#000000'); $('.goog-te-combo').attr('aria-label','google translate languages'); $('svg.goog-te-spinner').attr('title','Google Translate Spinner'); $('.goog-te-gadget-simple.goog-te-menu-value span').css('color','#000000'); } $(function() { $.getScript("//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"); });</script><script type="text/javascript"> $(function () { document.cookie = "responsiveGhost=0; path=/"; }); $(window).on("load", function () { $('body').addClass('doneLoading').removeClass('hideContent'); if ($('#404Content').length > 0) $('div#bodyWrapper').css('padding', '0px'); }); </script> <script type="text/javascript">loadCSS('//fonts.googleapis.com/css?family=Lato:300,300italic,700,700italic,900,900italic,italic,regular|Libre+Baskerville:700,italic,regular|Roboto:700,900|Roboto+Condensed:700|Roboto+Slab:700|');</script> [{"WidgetSkinID":56,"ComponentType":0,"FontFamily":"","FontVariant":"","FontColor":"","FontSize":0.00,"FontStyle":0,"TextAlignment":0,"ShadowColor":"","ShadowBlurRadius":0,"ShadowSpreadRadius":0,"ShadowOffsetX":0,"ShadowOffsetY":0,"ShadowInset":false,"ShadowColor2":"","ShadowBlurRadius2":0,"ShadowSpreadRadius2":0,"ShadowOffsetX2":0,"ShadowOffsetY2":0,"ShadowInset2":false,"ShadowColor3":"","ShadowBlurRadius3":0,"ShadowSpreadRadius3":0,"ShadowOffsetX3":0,"ShadowOffsetY3":0,"ShadowInset3":false,"ShadowColor4":"","ShadowBlurRadius4":0,"ShadowSpreadRadius4":0,"ShadowOffsetX4":0,"ShadowOffsetY4":0,"ShadowInset4":false,"ShadowColor5":"","ShadowBlurRadius5":0,"ShadowSpreadRadius5":0,"ShadowOffsetX5":0,"ShadowOffsetY5":0,"ShadowInset5":false,"Capitalization":0,"HeaderMiscellaneousStyles1":"","HeaderMiscellaneousStyles2":"","HeaderMiscellaneousStyles3":"","BulletStyle":0,"BulletWidth":2.00,"BulletColor":"","LinkNormalColor":"","LinkNormalUnderlined":false,"LinkNormalMiscellaneousStyles":"","LinkVisitedColor":"","LinkVisitedMiscellaneousStyles":"","LinkHoverColor":"","LinkHoverUnderlined":false,"LinkHoverMiscellaneousStyles":"","LinkSelectedUnderlined":false,"ForceReadOnLinkToNewLine":false,"DisplayColumnSeparator":false,"ColumnSeparatorWidth":0.0000,"HoverBackgroundColor":"","HoverBackgroundGradientStartingColor":"","HoverBackgroundGradientEndingColor":"","HoverBackgroundGradientDirection":0,"HoverBackgroundGradientDegrees":0.0000000,"HoverBackgroundImageFileName":"","HoverBackgroundImagePositionXUseKeyword":true,"HoverBackgroundImagePositionXKeyword":0,"HoverBackgroundImagePositionX":{"Value":0.0000,"Unit":0},"HoverBackgroundImagePositionYUseKeyword":true,"HoverBackgroundImagePositionYKeyword":0,"HoverBackgroundImagePositionY":{"Value":0.0000,"Unit":0},"HoverBackgroundImageRepeat":0,"HoverBorderStyle":0,"HoverBorderWidth":0,"HoverBorderColor":"","HoverBorderSides":15,"HoverBorderRadiusTopLeft":{"Value":null,"Unit":1},"HoverBorderRadiusTopRight":{"Value":null,"Unit":1},"HoverBorderRadiusBottomRight":{"Value":null,"Unit":1},"HoverBorderRadiusBottomLeft":{"Value":null,"Unit":1},"SelectedBackgroundColor":"","SelectedBackgroundGradientStartingColor":"","SelectedBackgroundGradientEndingColor":"","SelectedBackgroundGradientDirection":0,"SelectedBackgroundGradientDegrees":0.0000000,"SelectedBackgroundImageFileName":"","SelectedBackgroundImagePositionXUseKeyword":true,"SelectedBackgroundImagePositionXKeyword":0,"SelectedBackgroundImagePositionX":{"Value":0.0000,"Unit":0},"SelectedBackgroundImagePositionYUseKeyword":true,"SelectedBackgroundImagePositionYKeyword":0,"SelectedBackgroundImagePositionY":{"Value":0.0000,"Unit":0},"SelectedBackgroundImageRepeat":0,"SelectedBorderStyle":0,"SelectedBorderWidth":0,"SelectedBorderColor":"","SelectedBorderSides":15,"SelectedBorderRadiusTopLeft":{"Value":null,"Unit":1},"SelectedBorderRadiusTopRight":{"Value":null,"Unit":1},"SelectedBorderRadiusBottomRight":{"Value":null,"Unit":1},"SelectedBorderRadiusBottomLeft":{"Value":null,"Unit":1},"HoverFontFamily":"","HoverFontVariant":"","HoverFontColor":"","HoverFontSize":0.00,"HoverFontStyle":0,"HoverTextAlignment":0,"HoverShadowColor":"","HoverShadowBlurRadius":0,"HoverShadowSpreadRadius":0,"HoverShadowOffsetX":0,"HoverShadowOffsetY":0,"HoverShadowInset":false,"HoverShadowColor2":"","HoverShadowBlurRadius2":0,"HoverShadowSpreadRadius2":0,"HoverShadowOffsetX2":0,"HoverShadowOffsetY2":0,"HoverShadowInset2":false,"HoverShadowColor3":"","HoverShadowBlurRadius3":0,"HoverShadowSpreadRadius3":0,"HoverShadowOffsetX3":0,"HoverShadowOffsetY3":0,"HoverShadowInset3":false,"HoverShadowColor4":"","HoverShadowBlurRadius4":0,"HoverShadowSpreadRadius4":0,"HoverShadowOffsetX4":0,"HoverShadowOffsetY4":0,"HoverShadowInset4":false,"HoverShadowColor5":"","HoverShadowBlurRadius5":0,"HoverShadowSpreadRadius5":0,"HoverShadowOffsetX5":0,"HoverShadowOffsetY5":0,"HoverShadowInset5":false,"HoverCapitalization":0,"SelectedFontFamily":"","SelectedFontVariant":"","SelectedFontColor":"","SelectedFontSize":0.00,"SelectedFontStyle":0,"SelectedShadowColor":"","SelectedShadowBlurRadius":0,"SelectedShadowSpreadRadius":0,"SelectedShadowOffsetX":0,"SelectedShadowOffsetY":0,"SelectedShadowInset":false,"SpaceBetweenTabs":0,"SpaceBetweenTabsUnits":"","Trigger":4,"AnimationId":"00000000-0000-0000-0000-000000000000","AnimationClass":"animation00000000000000000000000000000000","ScrollOffset":80,"TriggerNameLowerCase":"scroll","ParentComponentWithTrigger":null,"BackgroundColor":"rgb(44, 53, 62)","BackgroundGradientStartingColor":"","BackgroundGradientEndingColor":"","BackgroundGradientDirection":0,"BackgroundGradientDegrees":0.0000000,"BackgroundImageFileName":"","BackgroundImagePositionXUseKeyword":true,"BackgroundImagePositionXKeyword":0,"BackgroundImagePositionX":{"Value":0.0,"Unit":0},"BackgroundImagePositionYUseKeyword":true,"BackgroundImagePositionYKeyword":0,"BackgroundImagePositionY":{"Value":0.0,"Unit":0},"BackgroundImageRepeat":0,"BorderStyle":0,"BorderWidth":0,"BorderColor":"","BorderSides":15,"BorderRadiusTopLeft":{"Value":null,"Unit":1},"BorderRadiusTopRight":{"Value":null,"Unit":1},"BorderRadiusBottomRight":{"Value":null,"Unit":1},"BorderRadiusBottomLeft":{"Value":null,"Unit":1},"MarginTop":{"Value":null,"Unit":0},"MarginRight":{"Value":null,"Unit":0},"MarginBottom":{"Value":null,"Unit":0},"MarginLeft":{"Value":null,"Unit":0},"PaddingTop":{"Value":null,"Unit":0},"PaddingRight":{"Value":null,"Unit":0},"PaddingBottom":{"Value":null,"Unit":0},"PaddingLeft":{"Value":null,"Unit":0},"MiscellaneousStyles":"box-shadow: 0px 3px 6px #00000029;","RecordStatus":0}] 