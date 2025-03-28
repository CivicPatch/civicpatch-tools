<script>jQuery(document).click(function (event) { var target = jQuery(event.target); if (target.attr('src') && target.parents('.image').length && target.parents('.widget').length) { var text = target.attr('title');  if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Image', eventAction: 'Image - ' + text, eventLabel: window.location.href }); } if (target.is('button') || target.hasClass('button') || target.parents().hasClass('button')) { var text = ""; if (target.parents('.button')[0]) { text = target.parents('.button').first().text(); } else if (target.text().length) { text = target.text(); } else if (target.attr('title').length) { text = target.attr('title'); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Button', eventAction: 'Button - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetCustomHtml').length) { ga('send', { hitType: 'event', eventCategory: 'Custom Html', eventAction: 'Custom Html Clicked', eventLabel: window.location.href }); } if (target.parents('.editor').length) { ga('send', { hitType: 'event', eventCategory: 'Editor', eventAction: 'Editor Link Clicked', eventLabel: window.location.href }); } if (target.parents('.GraphicLinks').length) { var text = ""; var targetGraphicLink = target; if (target.hasClass('widgetGraphicLinksLink')) { targetGraphicLink = jQuery(target.children()[0]); } if (targetGraphicLink.hasClass('text')) { text = targetGraphicLink.text(); } else if (targetGraphicLink.attr('src').length) { if (targetGraphicLink.attr('alt').length) { text = targetGraphicLink.attr('alt'); } else { text = targetGraphicLink.attr('src'); } } else { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Graphic Links', eventAction: 'Graphic Link - ' + text, eventLabel: window.location.href }); } if (target.parents('.InfoAdvanced').length) { ga('send', { hitType: 'event', eventCategory: 'Info Advanced', eventAction: 'Info Advanced Clicked', eventLabel: window.location.href }); } if (target.parents('.list').length) { ga('send', { hitType: 'event', eventCategory: 'List', eventAction: 'List Clicked', eventLabel: window.location.href }); } if (target.parents('.megaMenuItem').length || target.parents('.topMenuItem').length) { var megaMenuText = jQuery('.topMenuItem.mouseover').find('span').text(); var breadCrumbs = []; jQuery('.breadCrumbs > li').each(function () {  breadCrumbs.push(this.textContent); }); var pageTitle = breadCrumbs.join('>'); var subTitleText = target.parents('.megaMenuItem').children('.widgetTitle').children().text(); var text = ""; if (pageTitle) { text += pageTitle + " | "; } else { text += document.title + ' - '; } if (target.text() == "" && megaMenuText == "") { text += "N/A"; } else if (target.text().length && megaMenuText.length) { if (megaMenuText == target.text()) { text += megaMenuText; } else { text += megaMenuText + " - " + subTitleText + " - " + target.text(); } } else if (target.text() == "") { text += megaMenuText; } else { text += target.text(); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Mega Menu', eventAction: 'Mega Menu : ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetNewsFlash').length && target.parents('.widgetItem').length) { var text = jQuery(target.parents('.widgetItem')[0]).find('.widgetTitle').children().text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'News Flash', eventAction: 'News Flash - ' + text, eventLabel: window.location.href }); } if (target.hasClass('widgetQuickLinksLink') || target.find('.widgetQuickLinksLink').length) { var text = target.text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Quick Links', eventAction: 'Quick Links - ' + text, eventLabel: window.location.href }); } if (target.attr('src') && target.parents('.cpSlideshow').length) { var text = target.attr('title'); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Slideshow', eventAction: 'Slideshow - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetText').length) { ga('send', { hitType: 'event', eventCategory: 'Text', eventAction: 'Text Link Clicked', eventLabel: window.location.href }); }});</script>  [Skip to Main Content](https://www.redmond.gov/CivicAlerts.aspx?AID=2239#contentarea)   [![Emergency Alert](images/f4b5d2ae8474c05e5e31a78595368f26c24f59f2fc9a59746d10c354ab3ef3d9)Info](https://www.redmond.gov/2241)   [Immigration ResourcesClick for more information](https://www.redmond.gov/AlertCenter.aspx?AID=Immigration-Resources-78)   [![Redmond Washington Homepage](images/1aeb64d48825ffeb8bafff60e719fe9cae11b424bce2a83cb4a81b81765c4abf)](https://www.redmond.gov/CivicAlerts.aspx?AID=2239)  

 1.  [News](https://www.redmond.gov/CivicAlerts.aspx?AID=2239) 
 1.  [I Want To...](https://www.redmond.gov/9/I-Want-To) 
 1.  [Community](https://www.redmond.gov/101/Community) 
 1.  [Business](https://www.redmond.gov/35/Business) 
 1.  [Government](https://www.redmond.gov/27/Government) 
<script type="text/javascript"> document.addEventListener('DOMContentLoaded',function () { var menuID = 'mainNavMenu'; var menuType = MAIN_MENU; //setup menu manager properties for main menu if (!menuManager.mobileMainNav && true) menuManager.adjustMainItemsWidth('#' + menuID); menuManager.isMainMenuEditable = false; menuManager.mainMenuMaxSubMenuLevels = 4; menuManager.setMOMMode(2, menuType); //Init main menu var setupDraggable = menuManager.isMainMenuEditable; var urlToGetHiddenMenus = '/Pages/MenuMain/HiddenMainSubMenus?pageID=1&moduleID=1&themeID=57&menuContainerID=mainNav'; menuManager.setupMenu(menuID, 'mainNav', menuType, setupDraggable, urlToGetHiddenMenus); menuManager.mainMenuInit = true; menuManager.mainMenuTextResizer = true; if (1.00 > 0) menuManager.mainMenuTextResizerRatio = 1.00; if (window.isResponsiveEnabled) menuManager.mainMenuReady.resolve(); }); </script> <script async="" src="https://cse.google.com/cse.js?cx=001121890526140639040:zh3by1d9q84"></script>  []()  []()  <script type="text/javascript"> $(window).on("load", function () { $.when(window.Pages.rwdSetupComplete).done(function () { renderExternalBannerSlideshow('banner1', {"BannerOptionID":712,"ThemeID":57,"SlotName":"banner1","Name":"Default","IsDefault":true,"BannerMode":2,"SlideShowSlideTiming":"5","SlideshowTransition":0,"SlideShowTransitionTiming":"1","ImageScale":true,"ImageAlignment":1,"ImageScroll":true,"MuteSound":true,"VideoType":0,"Status":40,"SlideshowControlsPosition":0,"SlideshowControlsAlignment":0,"SlideshowBannerControlsColorScheme":0,"DisplayVideoPauseButton":false,"VideoPauseButtonAlignment":1,"VideoPauseButtonControlsAlignment":0,"VideoPauseButtonStyle":"#FFFFFF","VideoPauseButtonBackgroundStyle":"#000000","VideoPauseButtonAlignmentClass":"alignRight viewport","DisplaySlideshowPauseButton":false,"SlideshowControlsColor":"#FFFFFF","SlideshowControlsBackgroundColor":"#000000","SlideshowPauseButtonClass":"isHidden","BannerImages":[{"BannerImageID":954,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36208","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":1,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":955,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36209","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":2,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":956,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36210","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":3,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""},{"BannerImageID":957,"BannerOptionID":712,"FileName":"/ImageRepository/Document?documentID=36211","Height":300,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":4,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/","AltText":""}],"BannerVideos":[],"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135568000000)\/"}, '/App_Themes/2025 - Simple/Images/', 'Rotating'); }); }); </script> 

 1.  [Home](https://www.redmond.gov/CivicAlerts.aspx?AID=2239) 
 1. News Flash
 <script type="text/javascript"><!-- var isie6 = false, isie7 = false, isie6or7 = false; var intCountryCode = 840; function setUrlLength(editor) { //Toggle Image Context Menu Items setMenuItems(editor); //setContentBackgroundColor(editor); removeIEParagraphs(editor); } function setUrlLengthAndToolToggle(editor) { var minToolsGroups = 2; // Number of MinimumSetOfTools tools groups.  // Hide the MinimumSetOfTools on load. var toolbar = editor.get_toolContainer(); // Get toolbar container. var toolgroups = toolbar.getElementsByTagName("UL"); // Get all toolgroups containers.  for (var i = toolgroups.length - 1; i >= minToolsGroups; i--) toolgroups[i].style.display = "none";  if (editor.isIE) { var elem = editor.get_element(); elem.style.height = "430px";  elem.style.minHeight = "430px"; }  // Toggle Image Context Menu Items. setMenuItems(editor); //setContentBackgroundColor(editor); removeIEParagraphs(editor); }//--></script><script src="/ScriptResource.axd?d=kB9kqJ8G5bbVUkLIbkM_oWnWnbqKfmnijNvsGOdktAJN6X3E4IB1Ohim-XfL1bXqyhvHpFA6calISmsC9Do0K1jLgqaX5q7C12oYcoh4sn7Rb0pnPcc8nqSRG7UU7_90wNYn3HODMfqBMb-_fPUnBOi0lNqIP-V5iT54maOgYENrXw1cY5S_BKzgEKHC0oaJ0c8919qI0FCmCP3OGvShdDSMG4Ugcx-gfnVT0scxcMGBbz99a6uiw_3nP-VsLsbWwdhtEpb7o0k09629luJjVJub_8Rxcey54Z4TXug-4PjZv-2tKlkixzjql8wiTe4mP9VgLO1pXyY20BKVwpRkD8OErQCEy_Ncn6XLVZRKhBUKaUh-qSShvq5dwhcOEfDuDbOk8K0LNIDT19SrfEiL3OEOre_183ge7-WreFhCnLbba8t7J3g_GxHH8h6_tiPN_-sv0gX-93CSvG6Zro_ES91NsNKn1vvoKHK9qmyw1MAU91rxqlCtoXJAtqpKcMih1HIupSwbnYeMdZ6WQIxsvNNHhpfuoMjaur6u0VrYAmtJYIAA2XtF1-Rsw64yk136yplYJFNKndmGvYDrPOdAWr62DbwZfVZ0k-dKZ9uE56dzOQRCS5g5PTU62iFnnXQeQqWDKMBuATfJcBvKIZDkIrS0ohTWuIz-eq7xXKyWjASPArtOIPELf8w9wDA7qDwkPgnLpAGgAzXAwtqw7bD5dGnOSIW6N8GqF8FNjXdMlF_GdxSUMh_T6pAa_T_pstGGOpVUyg36NnlrD6f1VhWq9bzb05Ix0kPiXJcxFHrAF3BqLEHInjYE9CXuhVA_tCSbNS-teTycuhdXs3AZmB5iHvpvdvtAzKYttSC4rR39Ip01" type="text/javascript"></script><script type="text/javascript"> Sys.WebForms.PageRequestManager.getInstance().add_beginRequest(beginRequest); Sys.WebForms.PageRequestManager.getInstance().add_pageLoaded(pageLoaded); </script> <script src="/1757422876.js" type="text/javascript"></script> 

### Module Search

 Enter Search Terms All categoriesHomeParks & RecRedmond Police BlotterEnvironmentNews ReleasesCommunity Resources and Servicescp-testRedmond in the News

### Tools

 1.  [RSS](https://www.redmond.gov/rss.aspx#rssCivicAlerts) 
 1.  [Notify Me®](https://www.redmond.gov/civicalerts.aspx?Mode=Subscribe) 
 1. 

### Categories

 1.  [All Categories](https://www.redmond.gov/CivicAlerts.aspx) 
 1.  [Home](https://www.redmond.gov/CivicAlerts.aspx?CID=1) 
 1.  [Parks & Rec](https://www.redmond.gov/CivicAlerts.aspx?CID=7) 
 1.  [Redmond Police Blotter](https://www.redmond.gov/CivicAlerts.aspx?CID=8) 
 1.  [Environment](https://www.redmond.gov/CivicAlerts.aspx?CID=10) 
 1.  [News Releases](https://www.redmond.gov/CivicAlerts.aspx?CID=11) 
 1.  [Community Resources and Services](https://www.redmond.gov/CivicAlerts.aspx?CID=12) 
 1.  [cp-test](https://www.redmond.gov/CivicAlerts.aspx?CID=13) 
 1.  [Redmond in the News](https://www.redmond.gov/CivicAlerts.aspx?CID=14) 

# News Flash

## Home

 Posted on: October 21, 2024 

### Learn How Mayor Birney is Enhancing Her Leadership

  ![Learn How Mayor Birney is Enhancing Her Leadership News Flash](images/f83b954efe6c9b233933f66ade3086c37da32b2f61359720581d119e4c1adf7a)  

Mayor Birney recently earned an Advanced Certificate of Municipal Leadership from the Association of Washington Cities (AWC) for her service on the board of Hopelink. AWC’s Certificate of Municipal Leadership program recognizes city and town elected officials for accomplishing training in five core areas: 

 * Roles, responsibilities, and legal requirements
 * Public sector resource management
 * Community planning and development
 * Effective local leadership
 * Diversity, equity, inclusion, and belonging 

Those who earn the advanced certificate have continued to strive for excellence by attending conferences and trainings, serving their community, and further developing leadership skills.  

  [Learn about AWC](https://www.facebook.com/AWCities/?utm_medium=email&utm_source=govdelivery)   [![Facebook](images/b045feaa859d1365ade037c83e9bd9dbc2ddb2a3742fd27921711d507ad831aa.png)](https://www.facebook.com/sharer/sharer.php?u=https%3a%2f%2fwww.redmond.gov%2fCivicAlerts.aspx%3fAID%3d2239&t=Check out this news article for Redmond, WA)  [![Twitter](images/089ae2b0cd5f75744152e5658ea78ee66c84922c9fef68f1f9a67ff573792d62.png)](https://twitter.com/share?url=https%3a%2f%2fwww.redmond.gov%2fCivicAlerts.aspx%3fAID%3d2239&text=Check out this news article for Redmond, WA)  [![Email](images/4faf67ce28294dc0f853a54b47df39a1f8e46e09f8fa1d7ba630f4d28b0854e4.png)](https://www.redmond.gov/CivicAlerts.aspx?AID=2239#) <script language="javascript" type="text/javascript" src="/Assets/Scripts/SocialShare.js"></script><script language="javascript" type="text/javascript"> $(document).ready(function () { var socialShareJs = new SocialShare(); socialShareJs.setup('Check out this news article for Redmond, WA', 'https://www.redmond.gov/CivicAlerts.aspx?AID=2239'); }); </script>  [⇐PreviousFall Back and Change Your Batteries](https://www.redmond.gov/CivicAlerts.aspx?AID=2241)  [Next⇒City Council Vice President Jessica Forsythe Named Co-Chair of Eastrail](https://www.redmond.gov/CivicAlerts.aspx?AID=2238)  

## Other News in Home

  [![Mayor Birney Joins Greater Seattle Partners Board News Flash](images/b1777ecd299a38e0a2ec9a95f52447bed9aa228bcc3d33de2982bea9c4d78972)](https://www.redmond.gov/CivicAlerts.aspx?AID=2452) 

###  [Mayor Birney Joins Greater Seattle Partners Board](https://www.redmond.gov/CivicAlerts.aspx?AID=2452) 

 Posted on: March 24, 2025  [![Power Your Home with Solar News Flash](images/3ac7ffd8d1ebbeadffdb1a11664830a6a5ab0879258ca5a72b899d4171f50ee4)](https://olysol.org/solarize/eastside/?utm_medium=email&utm_source=govdelivery) 

###  [Power Your Home with Solar](https://olysol.org/solarize/eastside/?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 24, 2025  [![Have an Egg-cellent Time News Flash](images/81f6dcde65daceab87fa38b68b93fe25ecdfe4b1bd0d62fda50c069a43ee620b)](https://app.amilia.com/store/en/city-of-redmond/shop/activities/5584291) 

###  [Have an Egg-cellent Time](https://app.amilia.com/store/en/city-of-redmond/shop/activities/5584291) 

 Posted on: March 24, 2025  [![Summer Activities News Flash](images/7e1410934cafd14b42cb68184c590988f8b0fec84aff3c20b4706493f8994a47)](https://www.redmond.gov/1156/Summer-Camps) 

###  [Register for Summer Activities](https://www.redmond.gov/1156/Summer-Camps) 

 Posted on: March 24, 2025  [![Redmond Firefighters Climb for a Cure News Flash](images/c68b19362b210ec1bb5d98c05acfffade71b2002f3d2db146e07718e2f76ffe6)](https://www.lls.org/mission) 

###  [Redmond Firefighters Climb for a Cure](https://www.lls.org/mission) 

 Posted on: March 24, 2025  [![Ride the 2 Line to Marymoor Village and Downtown Redmond](images/4e3d56cb422b8282546c130c1e89036ea858f3a6e2f6d6695c575126002efbb6)](https://www.soundtransit.org/ride-with-us/know-before-you-go/how-to-ride) 

###  [Ride the 2 Line to Marymoor Village and Downtown Redmond](https://www.soundtransit.org/ride-with-us/know-before-you-go/how-to-ride) 

 Posted on: March 17, 2025  [![Teen Programs Moving from Old Fire House](images/23b1f4495547260902a6327ea24449ac39744d0720b8322bf5f6afe65d5fd661)](https://www.redmond.gov/2262/Teen-Services?utm_medium=email&utm_source=govdelivery) 

###  [Teen Programs Moving from Old Fire House](https://www.redmond.gov/2262/Teen-Services?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 17, 2025  [![Learn How Mayor Birney is Advancing Solutions for Housing Supply Challenges](images/262d8cc0a0381ae2c3c13b6b9ed0e01e7dc6bdb1e0be8a6184f148a814d36699)](https://www.redmond.gov/CivicAlerts.aspx?AID=2442&utm_medium=email&utm_source=govdelivery) 

###  [Learn How Mayor Birney is Advancing Solutions for Housing Supply Challenges](https://www.redmond.gov/CivicAlerts.aspx?AID=2442&utm_medium=email&utm_source=govdelivery) 

 Posted on: March 17, 2025  [![Learn How Redmonds Spaces and Buildings Will be Redesigned](images/82b485505dd35b4482c60b803700e59fd89e92835277d83388b98aa65d8f8ae8)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Learn How Redmond's Spaces and Buildings Will be Redesigned](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: March 17, 2025 | Last Modified on: March 17, 2025  [![Drones as First Responders Program Reached New Heights](images/25b1a346b41e5e091af999b9f3c5dd6a8e90c9133443c35c5f60afeb21b6dc34)](https://www.redmond.gov/2161/Drone-Program) 

###  [Drones as First Responders Program Reached New Heights in 2024](https://www.redmond.gov/2161/Drone-Program) 

 Posted on: March 17, 2025  [![Summer Camp Registration News Flash](images/614b89be7a54081fc99c9a24379eb272e4777779c1b8b14030ef461946f1940e)](https://app.amilia.com/store/en/city-of-redmond/shop/programs/112728) 

###  [Register for Summer Activities](https://app.amilia.com/store/en/city-of-redmond/shop/programs/112728) 

 Posted on: March 11, 2025  [![Here in Redmond March News Flash](images/fd361013c075a037747fc64157043519bfc8891dfb5de24adddda5d8587f8abf)](https://www.youtube.com/watch?v=Li_Y0KSUHVY) 

###  [Helping Put Food on the Table for Those in Need](https://www.youtube.com/watch?v=Li_Y0KSUHVY) 

 Posted on: March 10, 2025  [![Get Involved with Derby Days News Flash](images/84d4f201f0c697a2baee3f483e0f663e6468c746127f8bd4893c10d8e8086a9d)](https://www.redmond.gov/1174/Get-Involved) 

###  [Get Involved with Derby Days](https://www.redmond.gov/1174/Get-Involved) 

 Posted on: March 10, 2025  [![Beat the Bunny News Flash](images/94c5b884fa1b066cba6efb960a12c71c39997143256bb3d5b640b8a94568dfe6)](https://app.amilia.com/store/en/city-of-redmond/shop/programs/108545?subCategoryIds=5610392) 

###  [Register Today for the Beat the Bunny Race](https://app.amilia.com/store/en/city-of-redmond/shop/programs/108545?subCategoryIds=5610392) 

 Posted on: March 10, 2025 | Last Modified on: March 10, 2025  [![Safer Streets Speed Cameras News Flash](images/807033011eb0999595f6f154176d515a074665fd2c52a1b030b9bcca2434ee02)](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks) 

###  [Help Keep Our Streets Safe](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks) 

 Posted on: March 10, 2025  [![CNN News Flash](images/0f4378064dc0d509dc5d0becde0fc38fb1fb70d2d0f1d716730e1f6228ff66df)](https://www.youtube.com/@CityofRedmond) 

###  [Watch City News Now](https://www.youtube.com/@CityofRedmond) 

 Posted on: March 10, 2025  [![March Milestones News Flash](images/5e6df08d7a42a888e74fd9abfebd55fd0f4cddcb68ce7fdf31ff4cab5ec64a59)](https://www.redmond.gov/2258/Recognition-Months-Weeks-and-Days?utm_medium=email&utm_source=govdelivery#march) 

###  [Celebrate March Milestones](https://www.redmond.gov/2258/Recognition-Months-Weeks-and-Days?utm_medium=email&utm_source=govdelivery#march) 

 Posted on: March 3, 2025  [![CNN News Flash](images/ce05bd8cca6a1c9f658750fcccbcef41fe11f2a82c5ea5c29ff8b33b35d2fee5)](https://www.facebook.com/CityOfRedmond?utm_medium=email&utm_source=govdelivery) 

###  [Introducing City News Now](https://www.facebook.com/CityOfRedmond?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025  [![Safer Streets Speed Cameras News Flash](images/5cf54f87f5f1558c295999117e037a0c8c29c6b39f22cdcb241ff7c56fd4ff19)](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks?utm_medium=email&utm_source=govdelivery) 

###  [Help Keep Our Streets Safe](https://www.letsconnectredmond.com/ssap/surveys/traffic-safety-near-schools-and-parks?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025  [![Storm Drain News Flash](images/1358b235ebfb623b6af745d31a38dbd9d99efa0862c21fa94bed8ab1b19ba509)](https://www.redmond.gov/410/NPDES-Stormwater-Permit?utm_medium=email&utm_source=govdelivery#IDDE) 

###  [Take Action to Curb Pollution](https://www.redmond.gov/410/NPDES-Stormwater-Permit?utm_medium=email&utm_source=govdelivery#IDDE) 

 Posted on: March 3, 2025  [![Heat Pumps News Flash](images/74dff298cae26a02a123384dd7fa05a86616029aebf32a7ecb188635f9abb4e7)](https://events.gcc.teams.microsoft.com/event/23d3b9a2-fedc-4492-a88c-c23c5a52fc08@222d2edd-8255-45bd-8597-52141b82f713?utm_medium=email&utm_source=govdelivery) 

###  [Learn How You Can Get a Heat Pump in a Qualified Adult Family Home](https://events.gcc.teams.microsoft.com/event/23d3b9a2-fedc-4492-a88c-c23c5a52fc08@222d2edd-8255-45bd-8597-52141b82f713?utm_medium=email&utm_source=govdelivery) 

 Posted on: March 3, 2025 | Last Modified on: March 3, 2025  [![Learn How the City is Planning for Safer Streets News Flash](images/af158909a0d1a7d29296398be87a1972f937109919bbe267d1406dd93ed000b9)](https://www.redmond.gov/1152/Safer-Streets-Redmond) 

###  [Learn How the City is Planning for Safer Streets](https://www.redmond.gov/1152/Safer-Streets-Redmond) 

 Posted on: February 24, 2025  [![Take Action to Curb Pollution News Flash](images/fd7cfd2b0d0a432ed5bb9cfc60920a5f82fdec50c2a3e4dab6c9a30551aedecf)](https://www.facebook.com/watch/?v=600264416229252&rdid=yF86qTeW5zcDcovk) 

###  [Meet Our New Electric Fire Engine](https://www.facebook.com/watch/?v=600264416229252&rdid=yF86qTeW5zcDcovk) 

 Posted on: February 24, 2025  [![Get Help With Your Taxes News Flash](images/0ed5adab1dea3378e0b4f4f17a6efa3493307beaeb85ee8d1a28ca92515d9dba)](https://www.uwkc.org/need-help/tax-help/?utm_medium=email&utm_source=govdelivery) 

###  [Get Help With Your Taxes](https://www.uwkc.org/need-help/tax-help/?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 24, 2025 | Last Modified on: February 24, 2025  [![How Redmond Planned for Light Rail News Flash](images/d8f937b4c223d2d7b9cd31add9c9d8136e1a6d6e0e6384d79aa883fdfee03274)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Learn How Redmond Planned for Light Rail](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: February 18, 2025  [![Review the Stormwater Management Plan News Flash](images/6697cdd7633908bb3d44a79368b26f4015f2323e90290aa7e75ae7a588925864)](https://www.redmond.gov/410/NPDES-Stormwater-Permit) 

###  [Review the Stormwater Management Plan](https://www.redmond.gov/410/NPDES-Stormwater-Permit) 

 Posted on: February 18, 2025  [![Apply to the next Startup425 Accelerator News Flash](images/7e9bef1c2964bc1d9676892edb2241d67391b289002df540db365796e9c5a103)](https://www.startup425.org/accelerator) 

###  [Apply to the Next Startup425 Accelerator](https://www.startup425.org/accelerator) 

 Posted on: February 18, 2025  [![Ways to Beat the Winter Blues News Flash](images/cc2dc30de1655c2398d988cdc465d4aad03c4fe491a39bee033b0df25c973b19)](https://www.youtube.com/watch?v=t2-0ElDgPzc) 

###  [Ways to Beat the Winter Blues](https://www.youtube.com/watch?v=t2-0ElDgPzc) 

 Posted on: February 10, 2025  [![Bike Silver Star News Flash](images/f356ccb7ebba3909ceb7493c42ced79da6799be76c8639d1b1ad039e30737893)](https://www.redmond.gov/CivicAlerts.aspx?AID=2382) 

###  [Redmond Recognized as a Silver-Level Bicycle Friendly Community](https://www.redmond.gov/CivicAlerts.aspx?AID=2382) 

 Posted on: February 10, 2025  [![Redmond 2050 TMP News Flash](images/5f29939242ede8d72c662b1f13f39ca4e30ab1d38276b3368f6cceebd5e5c0c3)](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire) 

###  [Learn How Redmond 2050 is Planning for Access to Centers and Light Rail](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire) 

 Posted on: February 10, 2025  ![Presidents Day News Flash](images/358e9d91906d4c5b4d9a16d10a0881f0305dbf761f6b6191fbaba91214d27498)  

###  [Observing Presidents Day](https://www.redmond.gov/CivicAlerts.aspx?AID=2399) 

 Posted on: February 10, 2025  [![Celebrate Black History Month News Flash](images/2c7a3c64f41966c3b1482067d113e9d55555d94796be0c41135ad07258c7aedf)](https://asalh.org/black-history-themes/?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Black History Month](https://asalh.org/black-history-themes/?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 3, 2025  [![New Electric Fire Truck Ushers in a New Era of Firefighting News Flash](images/4d95074219d05d0a0558d7068d70b68e7bc142cbdda2ad928515c76d5e14f407)](https://www.redmond.gov/CivicAlerts.aspx?AID=2390) 

###  [New Electric Fire Truck Ushers in a New Era of Firefighting](https://www.redmond.gov/CivicAlerts.aspx?AID=2390) 

 Posted on: February 3, 2025  [![Save the Date- Ride the Rails to Downtown Redmond in May News Flash](images/725a5583fad31071f1d992bbf087edb16e518ff0767efe05e4d868fe8c69af97)](https://www.soundtransit.org/get-to-know-us/news-events/news-releases/link-2-line-service-between-redmond-technology-station?utm_medium=email&utm_source=govdelivery) 

###  [Save the Date: Ride the Rails to Downtown Redmond in May](https://www.soundtransit.org/get-to-know-us/news-events/news-releases/link-2-line-service-between-redmond-technology-station?utm_medium=email&utm_source=govdelivery) 

 Posted on: February 3, 2025  [![Prevent Damage to Your Pipes News Flash](images/00fb25b507918b1896fb06303070d40056c8450bed0e9df12816a388a6e474d0)](https://www.redmond.gov/397/WastewaterSewer?utm_medium=email&utm_source=govdelivery#FOG) 

###  [Prevent Damage to Your Pipes](https://www.redmond.gov/397/WastewaterSewer?utm_medium=email&utm_source=govdelivery#FOG) 

 Posted on: February 3, 2025  ![Council Conversations News Flash](images/2db3f7b5f99b74adba7d7d7b707209459be08f5f3929176eb8ec68ff1ff182e5)  

###  [Thank You for Joining Us at the Council Conversations – Town Hall](https://www.redmond.gov/CivicAlerts.aspx?AID=2387) 

 Posted on: January 27, 2025  [![How Do You Use Transit News Flash](images/15dd69a64f7614b0e5f8e6fc13e0c896ecfb8fb473f13b90a3115a9aa452785c)](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire?utm_medium=email&utm_source=govdelivery) 

###  [How Do You Use Transit?](https://www.letsconnectredmond.com/tmp/surveys/2025-transportation-master-plan-transit-questionnaire?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 27, 2025  [![Social Media News Flash](images/c9fc0dc496154f66bacfb3ad0327f58de6b754c29ff6584b9e2878eea9a44e83)](https://www.facebook.com/CityOfRedmond) 

###  [Follow Us on Social Media](https://www.facebook.com/CityOfRedmond) 

 Posted on: January 27, 2025  [![Welcoming Community News Flash](images/a63fcd1054cb67da0573180fb547318cf14f8e94d99c6fea0579cb88d57daa41)](https://www.redmond.gov/2241/Immigration-Resources?utm_medium=email&utm_source=govdelivery) 

###  [Affirming Our Commitment to a Welcoming Community](https://www.redmond.gov/2241/Immigration-Resources?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  ![Learn How Fire Staffing Models Are Enhanced News Flash](images/c9f0e5fb2ae858d7b8faaf8a0c6074900542c4ca9a97fa45ef01cd4966d362fe)  

###  [Learn How Fire Department Staffing Models Are Enhanced](https://www.redmond.gov/CivicAlerts.aspx?AID=2374) 

 Posted on: January 21, 2025  [![Redmond 2050 Prepares Our City for Climate Change and Extreme Weather News Flash](images/0072e4c4020af5215571bb9ca73c9c12dfe77d26218f28a20625a44d95891876)](https://www.redmond.gov/DocumentCenter/View/35171/05---Climate-Resilience-and-Sustainability-Element---draft-50-PDF?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Prepares Our City for Climate Change and Extreme Weather](https://www.redmond.gov/DocumentCenter/View/35171/05---Climate-Resilience-and-Sustainability-Element---draft-50-PDF?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  [![Disaster Assistance New Flash](images/e9513d0f0a6a48120b2cb3d4427fd2510218a999941d9b45861512d0252c973d)](https://kcemergency.com/2025/01/07/state-financial-assistance-available-to-those-severely-impacted-by-the-november-bomb-cyclone/?utm_medium=email&utm_source=govdelivery) 

###  [Apply for Disaster Assistance: Governor's Proclamation Provides Aid for Bomb Cyclone Victims](https://kcemergency.com/2025/01/07/state-financial-assistance-available-to-those-severely-impacted-by-the-november-bomb-cyclone/?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 21, 2025  [![1-13 HIR News Flash](images/0650e6fb876a17c3746044ffffe4fc8ea5e6fffeb563bb3b63afd57f7ad756b4)](https://youtu.be/24dLNko-c4o?si=kzUD1-2k_1XcvNXw) 

###  [Here in Redmond: Take a Look Back at 2024](https://youtu.be/24dLNko-c4o?si=kzUD1-2k_1XcvNXw) 

 Posted on: January 13, 2025 | Last Modified on: January 13, 2025  [![1-13 MLK Day News Flash](images/d3b547036a911ed32a5d0cfdcbf11ba512c41801d68cd6a4b27543922c6680df)](https://www.redmond.gov/DocumentCenter/View/36085/Martin-Luther-King-Jr-Day-of-Service-Proclamation-12025?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Martin Luther King Jr.](https://www.redmond.gov/DocumentCenter/View/36085/Martin-Luther-King-Jr-Day-of-Service-Proclamation-12025?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 13, 2025  [![1-13 Firefighters Deployed News Flash](images/e4173ae2ed0b997b82140f23417e31efff3e7a1026e07278ec196e6b00c54fe0)](https://www.redmond.gov/CivicAlerts.aspx?AID=2366&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Fire Department Deployed Crew to Support California Wildfires](https://www.redmond.gov/CivicAlerts.aspx?AID=2366&utm_medium=email&utm_source=govdelivery) 

 Posted on: January 13, 2025  [![1-13 Redmond 2050 Outdoor Amenities News Flash](images/d2a15558e0a6a2b0380e569c155c4a877185f3dcdefb4e10045ba6f8f4ef347f)](https://www.redmond.gov/1609/Parks-Arts-and-Culture) 

###  [Learn How Redmond 2050 Creates More Access to Outdoor Amenities and Nature](https://www.redmond.gov/1609/Parks-Arts-and-Culture) 

 Posted on: January 13, 2025  [![Zoning News Flash](images/7ce1a4132c4ef2848bfebc310e1cc0cbcbce559333c48bb7639ddd36c56ab0c4)](https://www.redmond.gov/2132/2024-Code-Updates?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Zoning and Other Regulatory Changes Effective January 1](https://www.redmond.gov/2132/2024-Code-Updates?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  ![Winter Weather News Flash](images/84aa0f8af8c40bd81768bb8a48bb38c0759abf4bdfd4f6c30172bf251ff94299)  

###  [Be Prepared for Winter Weather](https://www.redmond.gov/CivicAlerts.aspx?AID=2362) 

 Posted on: January 6, 2025  [![Come Play with Us News Flash](images/aea3659f0ad1f8a6c0d154a32b0f387e859d7651bb3a0d538d20c9e80f15abc4)](https://app.amilia.com/store/en/city-of-redmond/shop/programs?utm_medium=email&utm_source=govdelivery) 

###  [Come Play With Us This Winter](https://app.amilia.com/store/en/city-of-redmond/shop/programs?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  [![Fitness News Flash](images/8e88d08eb73f6f8f4497533de46ae742a35899dc70a0eea3f50881547db1baee)](https://app.amilia.com/store/en/city-of-redmond/shop/memberships?) 

###  [Reach Your New Year Fitness Goals](https://app.amilia.com/store/en/city-of-redmond/shop/memberships?) 

 Posted on: January 6, 2025  [![Adopt-A-Drain News Flash](images/59c46821ac9374272f5aef82a50b24cfe7647851b1e687672d85a38210935146)](https://wa.adopt-a-drain.org/?utm_medium=email&utm_source=govdelivery) 

###  [Make a Difference in Your Neighborhood](https://wa.adopt-a-drain.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: January 6, 2025  ![Share Your Photos News Flash](images/f9ef1671ce16981a4dd6f8943726818e141769533ee147af938e74c34d990588)  

###  [Share Your Best Photos of 2024](https://www.redmond.gov/CivicAlerts.aspx?AID=2353) 

 Posted on: December 30, 2024  [![Storm Support News Flash](images/b8a138e1b2ac748e8efb0dded6cdba890a81985313f4ec4992294358f0d7ecc2)](https://www.sba.gov/article/2024/12/23/sba-offers-disaster-assistance-washington-businesses-residents-affected-bomb-cyclone?utm_medium=email&utm_source=govdelivery) 

###  [Support Available for Residents and Businesses Impacted by the November Windstorm](https://www.sba.gov/article/2024/12/23/sba-offers-disaster-assistance-washington-businesses-residents-affected-bomb-cyclone?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024  [![Utilit Billing News Flash](images/568ec58588c828cc9179c59c0dde0cde18fec1c490fafdadee48e9d031b8ee8f)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024  [![ROW Fees News Flash](images/58a063c037970c5c4bcb4db1dee7e85549a0b4a2729c6a79ab1fc55a9ee074d2)](https://www.redmond.gov/372/Right-of-Way-Use-Permit?utm_medium=email&utm_source=govdelivery) 

###  [New Right of Way Use Fees Take Effect](https://www.redmond.gov/372/Right-of-Way-Use-Permit?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 30, 2024 | Last Modified on: December 30, 2024  [![Lightrail News Flash](images/28332f7dceffb04e30c3941de243b920d3bb9205f429a33f98cf16e41027ec84)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#lightrail) 

###  [Light Rail is Coming to Downtown Redmond](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#lightrail) 

 Posted on: December 23, 2024  [![Budget News Flash](images/d3b8bd79a7261d7d1fc7d212efb126dc3de627d7d30ac3f17eac63f492954640)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#budget) 

###  [Learn About Our New Budget](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#budget) 

 Posted on: December 23, 2024  [![Crows News Flash](images/bdb2dae92ebc88a598e5a285e9757b73b7e50b003fbbe672f5437ef386c99ec0)](https://www.instagram.com/p/DDlRJVEvfdf/?utm_medium=email&utm_source=govdelivery) 

###  [Check Out How Many Crows Are Roosting in Redmond](https://www.instagram.com/p/DDlRJVEvfdf/?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 23, 2024  ![Card Fees News Flash](images/10708031a12df581f05f3aa1ff59423887d5aac145546a6a7ed965cd4427283a)  

###  [New Card Service Fees Begin on January 2](https://www.redmond.gov/CivicAlerts.aspx?AID=2345) 

 Posted on: December 23, 2024  [![Protect Your Pipes from Winter Weather News flash](images/309b5b56480eb41896480e112bf8ad30fc337998a7d9f4121dcd44ad2b99364f)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#pipes) 

###  [Protect Your Pipes from Winter Weather](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#pipes) 

 Posted on: December 16, 2024  [![See How Redmond is Implementing Accessibility Improvements News Flash](images/993263fee96ec1e329d819e2cce79c36342c063cae561c689c25a319dbdfd81e)](https://www.redmond.gov/2057/31236/Inclusive-Design) 

###  [See How Redmond is Implementing Accessibility Improvements](https://www.redmond.gov/2057/31236/Inclusive-Design) 

 Posted on: December 16, 2024  [![Learn About New Right of Way Use Fees News Flash](images/bb8af01df6b918cd8cda2308aa85e795a9076481a13f4dd5ca8824bee5c64241)](https://www.redmond.gov/2157/Right-of-Way-Use-Fee) 

###  [Learn About New Right of Way Use Fees](https://www.redmond.gov/2157/Right-of-Way-Use-Fee) 

 Posted on: December 16, 2024  [![Concrete Success News Flash](images/f170b42fff2af67bfc8f49a1100bc60a2cfcb0e4555098054cba318c1482e0c3)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#concrete) 

###  [See Concrete Crew Success Stories](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#concrete) 

 Posted on: December 9, 2024  [![EV News Flash](images/444512df2175cddf0264cf9cc2c76a1459202b3f61597d291efc0042a692a744)](https://www.letsconnectredmond.com/tmp/surveys/ev-charging?utm_medium=email&utm_source=govdelivery) 

###  [Share Your Thoughts on Electric Vehicles Infrastructure](https://www.letsconnectredmond.com/tmp/surveys/ev-charging?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024 | Last Modified on: December 9, 2024  [![Climate Heros News Flash](images/5ed29ecef05f5cba7bdf2112b2d4b7b0a0ee2b928191f497d20e0688f9336220)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#parks) 

###  [See How Parks Are Leading the Charge as Climate Heroes](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery#parks) 

 Posted on: December 9, 2024  [![Utility Billing News Flash](images/79022345b625dabba132dd9c43082c8fa5036c58157a195696a4c8fe58d1968b)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  [![Zoning Redmond 2050](images/4986842aa3b6123c222f855b6ddb23c5fd64c2e0504a8fbba5f01493a0f30f5c)](https://www.redmond.gov/2226/Vesting-to-the-Redmond-Zoning-Code?utm_medium=email&utm_source=govdelivery) 

###  [Learn About the Two Editions of the Redmond Zoning Code](https://www.redmond.gov/2226/Vesting-to-the-Redmond-Zoning-Code?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  ![Card Fees News Flash](images/fc28434f3b2d9e707081ae18345fced2225814d2cd326e3f999e66a28c20f687)  

###  [New Card Service Fees Begin January 2](https://www.redmond.gov/CivicAlerts.aspx?AID=2322) 

 Posted on: December 9, 2024  [![Energy Expense Help News Flash](images/5d46748f92b99d4169879a2c65c5ff19066b0a8cf478898f3511bb49b2fa1b3a)](https://www.hopelink.org/programs/energy/?utm_medium=email&utm_source=govdelivery) 

###  [Receive Help with Energy Expenses](https://www.hopelink.org/programs/energy/?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 9, 2024  ![Redmond Lights News Flash](images/cf3fc80948104be299cadc17430ed1cec7608280a5d3bcfc52219f66339ebd66)  

###  [Join Us at Redmond Lights](https://www.redmond.gov/CivicAlerts.aspx?AID=2303) 

 Posted on: December 2, 2024  [![FOCUS News Flash](images/e7b54e1a9c5b3d4a69f8e02d096a990b25b3a8365e5dd4399c3a7b66b3a4af1a)](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery) 

###  [Read the Latest Focus Newsletter](https://www.redmond.gov/2207/Focus---FallWinter-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 2, 2024  [![Be Prepared for Winter Weather NEws Flash](images/f224306285fb34d650a427fc9686e07a59dcdaffec2dce9ade3b9ff7768535bc)](https://www.redmond.gov/1315/Weather-Alert-Updates?utm_medium=email&utm_source=govdelivery) 

###  [Be Prepared for Winter Weather](https://www.redmond.gov/1315/Weather-Alert-Updates?utm_medium=email&utm_source=govdelivery) 

 Posted on: December 2, 2024  ![Meet Our New Snow Plows](images/debbfc2744e7c3f6ad4c82abee6958b9c17deb9949688780ec60fc7b6ac4dce2)  

###  [Meet Our New Snowplows](https://www.redmond.gov/CivicAlerts.aspx?AID=2300) 

 Posted on: December 2, 2024  ![Learn How Redmond 2050 Supports Local Businesses News Flash](images/f077a18da5a627eb38147f96dffb3004bca496eba1d3ff66377d84fc22163be4)  

###  [Learn How Redmond 2050 Supports Local Businesses](https://www.redmond.gov/CivicAlerts.aspx?AID=2299) 

 Posted on: December 2, 2024  ![Construction News Flash](images/19d8088f66146369868918ee073ff287e5b8ca02c0008146ea2010ed93066402)  

###  [Be Aware of Upcoming Construction](https://www.redmond.gov/CivicAlerts.aspx?AID=2297) 

 Posted on: December 2, 2024  [![Redmond Lights Newsflash](images/f03aad2a64f81e5abe320b98b881844c5d01875b1c4d328bd12fedb1e2b9a52e)](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Light and Art at Redmond Lights](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Shop Local News flash](images/3aa8322727b0bffda7cc415ce3101086694919f82d9874cf91e335454b31f466)](https://experienceredmond.com/Shop-Small/?utm_medium=email&utm_source=govdelivery) 

###  [Shop Local and Show Your Support](https://experienceredmond.com/Shop-Small/?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Comprehensive Plan News Flash](images/2e5f6b6763a71e8605af31ef6a83ac69fcb25ece68429ae60147a5bb82f851b8)](https://www.redmond.gov/CivicAlerts.aspx?AID=2274&utm_medium=email&utm_source=govdelivery) 

###  [View the Adopted Redmond 2050 Plan](https://www.redmond.gov/CivicAlerts.aspx?AID=2274&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![EMS Fees News Flash](images/238696c64d3b7b2982cb576336fdbefbb23df5e9533c1ed7091e48f3dc9a9986)](https://www.redmond.gov/faq.aspx?TID=106&utm_medium=email&utm_source=govdelivery) 

###  [Learn About EMS Transport Fees](https://www.redmond.gov/faq.aspx?TID=106&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  ![Happy Holidays News Flash](images/54c358cddfaaa60c4d2cd0779b8a25759955be9b5adaf293ea1dd0ae307db702)  

###  [Wishing You a Safe and Happy Holiday](https://www.redmond.gov/CivicAlerts.aspx?AID=2285) 

 Posted on: November 25, 2024  [![Help Others This Holiday News Flash](images/3ca7f38833d25154c3969dfe79ef6670ebde17c7f9f2eadb54b31d95301a6d8a)](https://www.redmond.gov/DocumentCenter/View/34804/Holiday-Giving-2024?utm_medium=email&utm_source=govdelivery) 

###  [Help Others During the Holidays](https://www.redmond.gov/DocumentCenter/View/34804/Holiday-Giving-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 25, 2024  [![Universal Design News Flash](images/88a86f00a27faed265df67696f9cff64d0ca446be769416feb9edcd2849d5ed2)](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond is Implementing Universal Design to Improve Accessibility and Inclusion](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  ![Card Fees News Flash](images/c6edafccb7791d6e757f9a07d8705c24311c94d9f2d992e94647d39b42fa0202)  

###  [New Card Service Fees Begin December 2](https://www.redmond.gov/CivicAlerts.aspx?AID=2266) 

 Posted on: November 18, 2024  [![TMP How you get around Redmond News Flash](images/d54dd48b00af65d58f6c2725e0dbf25025a974851a3fe2f5daa788282d5768e6)](https://www.letsconnectredmond.com/tmp?utm_medium=email&utm_source=govdelivery) 

###  [Share How You Get Around Redmond](https://www.letsconnectredmond.com/tmp?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  [![Stay Connected News Flash](images/9fc1946dbce9978133bc0da35cc2b8acf092bc9a4750eb36c4ba791d0afe08d1)](https://www.redmond.gov/208/Enews-Subscription?utm_medium=email&utm_source=govdelivery) 

###  [Stay Connected on Sustainability, Parks, Growth, and More](https://www.redmond.gov/208/Enews-Subscription?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 18, 2024  [![New Small Business News Flash](images/f7407c26535112f1725bf5056575b6827b3bf164ca8094f53ee02818b9f36d6e)](https://www.youtube.com/watch?v=s-F3WBuCFWg) 

###  [Check out Redmond’s Stylish New Small Business](https://www.youtube.com/watch?v=s-F3WBuCFWg) 

 Posted on: November 12, 2024  [![Firefighters Return News Flash](images/e1f62f8547692f1243654a8293e6ce7f5a9bb3d770e5f50c6bb3505762183917)](https://www.redmond.gov/CivicAlerts.aspx?AID=2255&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Firefighters Return from Hurricane Deployments](https://www.redmond.gov/CivicAlerts.aspx?AID=2255&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![Salary Commission News Flash](images/3ee88644eb49a4e229459b42bc8c6ce25f7b4d7fa0449f4855fbed78078e9716)](https://www.redmond.gov/1972/Salary-Commission?utm_medium=email&utm_source=govdelivery) 

###  [Salary Commission Completes its Work](https://www.redmond.gov/1972/Salary-Commission?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![Utility Billing News Flash](images/dde6ffd540140f3239a3cb79e83198a283e14bd619b92f368da27ab856133cb4)](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

###  [Be Aware of Changes to Utility Billing Payment Options](https://www.redmond.gov/FAQ.aspx?TID=107&utm_medium=email&utm_source=govdelivery) 

 Posted on: November 12, 2024  [![King County Alert News Flash](images/a44e4a8954bf11a22022b3b4fed24470bf1e60c465eba420256ca5e5fb563295)](https://kingcounty.gov/en/dept/executive-services/health-safety/safety-injury-prevention/emergency-preparedness/alert-king-county?utm_medium=email&utm_source=govdelivery) 

###  [Sign Up for Emergency Alerts](https://kingcounty.gov/en/dept/executive-services/health-safety/safety-injury-prevention/emergency-preparedness/alert-king-county?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  [![Native American Heritage News Flash](images/1c58b4f95f7daf7458292d3cd72e4da90543f708f0e0c030ec401c4ce472c908)](https://www.nativeamericanheritagemonth.gov/?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Native American Heritage Month](https://www.nativeamericanheritagemonth.gov/?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  [![Redmond 2050 News Flash](images/d21f7e92098a371308407b6cb1b194596ab6621576ce5edc9aa6160710a33c5a)](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Focuses on Equity and Inclusion](https://www.redmond.gov/2057/Inclusive-Design?utm_medium=email&utm_source=govdelivery) 

 Posted on: November 4, 2024  ![Credit Card Fees News Flash](images/417c5a8b903ff34f55b11e644322dfefb8e5cc66c5cde9b548d429ca70f72452)  

###  [New Card Service Fees Begin December 2](https://www.redmond.gov/CivicAlerts.aspx?AID=2249) 

 Posted on: November 4, 2024  ![Small Business Workshop News Flash](images/f861b6dabce1069bc33751949dd1e64714ed52d39530532a502bdff6dd125f5e)  

###  [Find Upcoming Opportunities for Redmond Businesses and Job Seekers](https://www.redmond.gov/CivicAlerts.aspx?AID=2248) 

 Posted on: November 4, 2024  [![Learn About the Impact of 2117 on Redmond News Flash](images/a43d3195392caa208e11b2448034e2cbee917a879243db431af9dce32b650f58)](https://www.redmond.gov/CivicAlerts.aspx?AID=2164&utm_medium=email&utm_source=govdelivery) 

###  [Learn About the Impact of 2117 on Redmond](https://www.redmond.gov/CivicAlerts.aspx?AID=2164&utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![See Environmental Sustainability Progress News Flash](images/af1661b70be6782a1041b9712442b5db54dec380cef4b494038561230f42f039)](https://www.redmond.gov/2182/2023-Environmental-Sustainability-Annual?utm_medium=email&utm_source=govdelivery) 

###  [See Environmental Sustainability Progress](https://www.redmond.gov/2182/2023-Environmental-Sustainability-Annual?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![Learn How Redmond Zones are Changing News Flash](images/abf60b70683d67ca49b67c8e5b7c45f64e719c403eede4505ba3824eda6cbcc3)](https://www.redmond.gov/2108/Mixed-use-zones?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond Zones are Changing](https://www.redmond.gov/2108/Mixed-use-zones?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 28, 2024  [![No Lead in Redmonds Service Lines Newsflash](images/2ae973e42ac08057b50447a9063970b67a31c3a083e9bca3a219c25349753f03)](https://www.redmond.gov/233/DrinkingWater?utm_medium=email&utm_source=govdelivery#lead) 

###  [No Lead in Redmond’s Service Lines](https://www.redmond.gov/233/DrinkingWater?utm_medium=email&utm_source=govdelivery#lead) 

 Posted on: October 28, 2024  ![Fall Back and Change Your Batteries News Flash](images/a52413a2f8cfaebb4b90d524e240c10520b98d2299e9f60b523672e034435848)  

###  [Fall Back and Change Your Batteries](https://www.redmond.gov/CivicAlerts.aspx?AID=2241) 

 Posted on: October 28, 2024  ![Jessica Forsythe News Flash](images/15c01a07962788736f3731ba6a931465d4ccd8a21e65736bf30c9a50833ea9be)  

###  [City Council Vice President Jessica Forsythe Named Co-Chair of Eastrail](https://www.redmond.gov/CivicAlerts.aspx?AID=2238) 

 Posted on: October 21, 2024  [![Redmond 2050 Zoning News Flash](images/50eac70e8c429c6013a10cd8db085ead43ab7c6c13c7d83fad4453abecfe6833)](https://www.redmond.gov/1606/Housing?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Redmond 2050 Will Change Zoning in the City](https://www.redmond.gov/1606/Housing?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 21, 2024  [![Heats Pumps this Winter News Flash](images/5fef5ffe99add6a09f8eff7d37c70c425a635fc486b39406d6541fc95bf7d5fb)](https://www.youtube.com/watch?v=U1bnOUMvrd8) 

###  [Stay Warm and Cozy with a Heat Pump](https://www.youtube.com/watch?v=U1bnOUMvrd8) 

 Posted on: October 21, 2024  ![Storm Drains News Flash](images/beb42cbcf21f4613964be04c9db9fdc87a32b1347b3e655e12006d16f7b1ac61)  

###  [Make a Difference in Your Neighborhood](https://www.redmond.gov/CivicAlerts.aspx?AID=2233) 

 Posted on: October 21, 2024  [![Best Pizza in Redmond News Flash](images/264196cdc8453422d6e93b91d6d53dff0bf0aaa70f9d8dab3dcb5cd0ba14f759)](https://www.youtube.com/watch?si=1cVJfAsopp2Ldksm&utm_medium=email&utm_source=govdelivery&v=A-pVY__DWi0&feature=youtu.be) 

###  [Learn Where to Find the Best Pizza in Redmond](https://www.youtube.com/watch?si=1cVJfAsopp2Ldksm&utm_medium=email&utm_source=govdelivery&v=A-pVY__DWi0&feature=youtu.be) 

 Posted on: October 14, 2024  ![Honoring Indigenous Peoples Day News Flash](images/2bf8370dabf4d75062a27f3643d0436c6c801cf593ff2c50e5b4546342539d47)  

###  [Honoring Indigenous Peoples Day](https://www.redmond.gov/CivicAlerts.aspx?AID=2230) 

 Posted on: October 14, 2024  [![Drop Take Cover News Flash](images/89980661b5e3ff9e2353c313a2218a2ee23611eabca2aee56b184e0fa54b8f8d)](https://www.youtube.com/playlist?list=PLs1gMujRSBY2t7JB4VS-AymFwN-6Lvg20) 

###  [Drop. Take Cover. Hold On.](https://www.youtube.com/playlist?list=PLs1gMujRSBY2t7JB4VS-AymFwN-6Lvg20) 

 Posted on: October 14, 2024  [![Read Local Eat Local News Flash](images/d61df8439f161ce10b3fb4f403a2dd0369c0d8f28e24e0f57921c5c8439960eb)](https://www.redmond.gov/2142/Read-Local-Eat-Local?utm_medium=email&utm_source=govdelivery) 

###  [Read Local Eat Local](https://www.redmond.gov/2142/Read-Local-Eat-Local?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Redmond Lights News Flash](images/880061398184368ebaf49e721a62b128e1858ed95ea1f2c76bb9115cbede8250)](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

###  [Get Ready to Glow](https://www.redmond.gov/1139/Redmond-Lights?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  ![Budget News Flash](images/8e750f40a2b6f0e59a8b620e52515106e27c862e8c55e40f0a145e18ee03469d)  

###  [Read the City’s Preliminary Budget](https://www.redmond.gov/CivicAlerts.aspx?AID=2217) 

 Posted on: October 7, 2024  [![Heat Pumps News Flash](images/063769da3199ab250e03ba8e78ea40660803564f452537f915d8fdb142752149)](https://www.redmond.gov/CivicAlerts.aspx?AID=2164) 

###  [Learn About the Impact of Initiative 2117 on Redmond](https://www.redmond.gov/CivicAlerts.aspx?AID=2164) 

 Posted on: October 7, 2024  [![Vent to Prevent News Flash](images/23485ceb54f425264200dfd1e58155c888d3b696e35e9c6686a4d1a3372f0ef9)](https://www.nfpa.org/education-and-research/home-fire-safety/smoke-alarms?utm_medium=email&utm_source=govdelivery) 

###  [Vent to Prevent](https://www.nfpa.org/education-and-research/home-fire-safety/smoke-alarms?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Cyber Security News Flash](images/de732c10ef449f8d202340660f6f311406c515be9eea4c1c1fda4833bb57e93e)](https://www.cisa.gov/cybersecurity-awareness-month?utm_medium=email&utm_source=govdelivery) 

###  [Stay Cyber Safe](https://www.cisa.gov/cybersecurity-awareness-month?utm_medium=email&utm_source=govdelivery) 

 Posted on: October 7, 2024  [![Fall Traffic Counts News Flash](images/aa6efa05d8e2bf81d2c41a8ff4469c25e64962436de16b4b144864d55f693a29)](https://www.redmond.gov/863/Traffic-Counts) 

###  [Learn About Redmond’s Fall Traffic Counts](https://www.redmond.gov/863/Traffic-Counts) 

 Posted on: September 30, 2024  [![Sign Up for Silver Sneakers](images/81f8b7a67b6a086ebccca8ca1753eed1716ddffb1c3d1341bf7c5036e6b8db57)](https://app.amilia.com/store/en/city-of-redmond/shop/memberships/52900) 

###  [Participate in SilverSneakers](https://app.amilia.com/store/en/city-of-redmond/shop/memberships/52900) 

 Posted on: September 30, 2024  [![Redmond 2050 News Flash](images/0adad11f0a9e4715f53ee5534cbeaa9e1f6e3dcf7fea2b9191af51eb6c64cd78)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Redmond 2050: What’s Changing in Your Neighborhood](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: September 30, 2024  [![Redmond Senior & Community Center Passes News Flash](images/f13f4717784eb4adcf38f57785f71a140957f57e15ae2aacedfd2d08468cf93e)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b7148f) 

###  [Learn About Our Redmond Senior & Community Center Passes](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b7148f) 

 Posted on: September 23, 2024  [![Redmond 2050 News Flash](images/882f31c185181088b8fe8124726ccca41e90caef8645d486f70607e282a7d8b4)](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

###  [Redmond 2050: What is a Complete Neighborhood?](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

 Posted on: September 23, 2024  [![Homelessness News Flash](images/36f700289075f8b1c294d4bc52e795ea3549cc382722c3ad64289388ea824934)](https://www.youtube.com/watch?v=w_SgXf3a5G8) 

###  [Be Part of the Solution to Homelessness](https://www.youtube.com/watch?v=w_SgXf3a5G8) 

 Posted on: September 23, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b69195) 

###  [Downtown Redmond Art Walk, Council Conversations, Redmond Lights, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b69195) 

 Posted on: September 18, 2024  [![Bike Survey](images/d7b2f5363262b08e24618950a88965d1a1d679af978bddc8e359370ed4fc5c38)](https://www.surveymonkey.com/r/BFC_2024?utm_medium=email&utm_source=govdelivery) 

###  [Take Part in Our Bike Friendly Communities Survey](https://www.surveymonkey.com/r/BFC_2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: September 16, 2024  [![Utility BillingNews Flash](images/4d98ce3eebbb28ff495cf983b5faa22d47b418d53e03d6c65743cc5e7aba8193)](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

###  [Learn About Changes to Utility Billing](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

 Posted on: September 16, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b4f2e9) 

###  [Fall Activities on the Farm, Council Conversations, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3b4f2e9) 

 Posted on: September 11, 2024  [![Here in Redmond Home Newsflash](images/4b2afd519255e8ad4d44ae63cadcb3e5ee794c8c9dc28cd19e20019bcb7dd7ed)](https://www.youtube.com/watch?v=Xd09oa44rDI) 

###  [A Sense of Home is Meaningful for Everyone](https://www.youtube.com/watch?v=Xd09oa44rDI) 

 Posted on: September 9, 2024  ![Remembering September 11 Newsflash](images/e204e2409beb4dee3b3999584cdc0de8a20533a02589f083c725ee1dc6f53690)  

###  [Remembering September 11](https://www.redmond.gov/CivicAlerts.aspx?AID=2172) 

 Posted on: September 9, 2024 | Last Modified on: September 9, 2024  ![Hispanic Heritage Month Newsflash](images/273ea2b4d5a4db9ea07d22def9e374f192a3c2b4a15689c811257d65f7a6e727)  

###  [Celebrate Hispanic Heritage Month](https://www.redmond.gov/CivicAlerts.aspx?AID=2170) 

 Posted on: September 9, 2024  [![Startup 425 Newsflash](images/402b3eb2df28bd595c6649b0cc4c28e6c15d62b4d0b2b77ddaa915bd5e258b31)](https://www.startup425.org/accelerator) 

###  [Learn About the Startup 425 Accelerator](https://www.startup425.org/accelerator) 

 Posted on: September 9, 2024  [![Safe Driving News Flash](images/da0d7769b4cdb47207fe0a37391a9ce6f036df2003b48f19c1b1969469d163c0)](https://www.goredmond.com/blog/august-25-2022-1108am/back-school-safety-tips) 

###  [Make Back-to-School Safe](https://www.goredmond.com/blog/august-25-2022-1108am/back-school-safety-tips) 

 Posted on: September 3, 2024  [![Salmon SEEson News Flash](images/2f3d5ec7c680beac41b4a14de5b12a80fc0dde90a5885b9bd79087cd13922d48)](https://experience.arcgis.com/experience/779f2239705a42fba71f198d958da479/?data_id=dataSource_2-Salmon_viewing_sites_8034%3A7) 

###  [Discover Salmon SEEson](https://experience.arcgis.com/experience/779f2239705a42fba71f198d958da479/?data_id=dataSource_2-Salmon_viewing_sites_8034%3A7) 

 Posted on: September 3, 2024  [![Ready Plan News Flash](images/a15926ffeb6974bab2875fe7cac0cce73acf8f7915bbc755d54381ab2ccad77e)](https://www.ready.gov/plan) 

###  [Take Control of Your Readiness](https://www.ready.gov/plan) 

 Posted on: September 3, 2024  [![Redmond 2050 News Flash](images/946e5d7b70fc0737ba5181e94953e59749a836f5f373dd4c7e773e51c460d2af)](https://www.redmond.gov/1427/Redmond-2050) 

###  [Nearing Completion: Learn the Latest About Redmond 2050](https://www.redmond.gov/1427/Redmond-2050) 

 Posted on: August 26, 2024  [![RSCC Membership News Flash](images/1075fa268766d6b0985407dd961e7208537c7df3dbc1056fee1e242239d78e81)](https://www.redmond.gov/2127/Hours-and-Operations) 

###  [Get a Membership to the Redmond Senior & Community Center](https://www.redmond.gov/2127/Hours-and-Operations) 

 Posted on: August 26, 2024  ![Safe Community News Flash](images/5b1405daf17fffcd9d279fedb7a211bbeac6127bd06cd9895016fb14b5bcfbf0)  

###  [Help Keep Our Community Safe](https://www.redmond.gov/CivicAlerts.aspx?AID=2154) 

 Posted on: August 26, 2024  [![Climate Mayors Electric Vehicle Commitment](images/56dceb35ba8d7405d9714583984ff8dbe805c993ea4d96f94e96cb5d514c0a0d)](https://www.climatemayors.org) 

###  [Learn About Climate Mayors Electric Vehicle Commitment](https://www.climatemayors.org) 

 Posted on: August 19, 2024  [![Bike Survey News Flash](images/0c72d5f7256aed6de1f439d11d4141d68808db7f7cbb5faf3eb15a39634494c3)](https://www.surveymonkey.com/r/BFC_2024) 

###  [Take Part in Our Bike Friendly Communities Survey](https://www.surveymonkey.com/r/BFC_2024) 

 Posted on: August 19, 2024  [![Utility Billing News Flash](images/b96a5050a4f3d243faa256135efcebf78f34c5bd30578cb667ebaf95f90679c7)](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

###  [Learn About Changes to Utility Billing](https://www.redmond.gov/2102/Frequently-Asked-Questions) 

 Posted on: August 19, 2024  [![Car Care to Protect Our Water News Flash](images/3723f9aa22a9f75487da26bee36b9f63f114489808bace061c898e437b0d7ad1)](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#car) 

###  [Care for Your Car to Protect Our Water](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#car) 

 Posted on: August 19, 2024  [![Poet Laureate Chin-in Chen News Flash](images/ba57de6612408585a73d1d2fa57fcf887a79511758cbd1e0020c268009c5f116)](https://poets.org/academy-american-poets-2024-poet-laureate-fellows) 

###  [Learn About Our Poet Laureate’s National Recognition](https://poets.org/academy-american-poets-2024-poet-laureate-fellows) 

 Posted on: August 12, 2024  [![NE 40th Street Underpass News Flash](images/e12ca582e50daf9eb0f9c8a871c16211a4735b5f06e5116aaee8b01fb994c080)](https://www.redmond.gov/1151/Light-Rail-Extension) 

###  [See the Newly Opened NE 40th Street Underpass](https://www.redmond.gov/1151/Light-Rail-Extension) 

 Posted on: August 12, 2024  ![NNO News Flash](images/f4dd771274a0d365e324eca7207e4bf362f38f09afa22550f2a6cde28521689c)  

###  [Thank You All for National Night Out](https://www.redmond.gov/CivicAlerts.aspx?AID=2137) 

 Posted on: August 12, 2024  [![8-12_Keep our Roads Safe_News Flash](images/e12f92b962a41c1037239197dcca537bcd91b7c6327b06011ded353e4e14ada9)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#driver-pedestrian) 

###  [Keep our Roads Safe](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#driver-pedestrian) 

 Posted on: August 12, 2024  [![Use Water Wisely News Flash](images/14bd10cbe3dea52fdde79524a7e0f65d87d3b8f15ae2cc0e085e0b5f0ed51616)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#water) 

###  [Use Water Wisely](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#water) 

 Posted on: August 12, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3ad380c) 

###  [Find your perfect fall activities and more!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3ad380c) 

 Posted on: August 7, 2024  [![Here in Redmond News Flash](images/42689d3cb3a8febe6bc1009adcd30deb3afe01280a2caa5446295f0a6f3daff0)](https://www.youtube.com/watch?v=YgjjZc7ATVM) 

###  [Keep Loved Ones Safe with the Take Me Home Program](https://www.youtube.com/watch?v=YgjjZc7ATVM) 

 Posted on: August 5, 2024  [![Budget Questionnaire](images/4b9a6677a1eaeb24bdd66ada4cbf548436648b8208ef8753c35f65bf90b5668a)](https://www.letsconnectredmond.com/budget-2024) 

###  [Share Your Budget Priorities with Us](https://www.letsconnectredmond.com/budget-2024) 

 Posted on: August 5, 2024  [![Community Survey Results News Flash](images/f5a36dcc214d1ff44493a59ecc882a65c9d6c214c6e5ee442bb187fee50a5c8f)](https://www.redmond.gov/856/Community-Surveys) 

###  [View the Annual Community Survey Results](https://www.redmond.gov/856/Community-Surveys) 

 Posted on: August 5, 2024  [![Stormwater, Streams, and More News Flash](images/4b46c4d43d35970ae40056c364682c4ea080aa7cf8852ecf2969054d97005cee)](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

###  [We Want to Hear from You about Stormwater, Streams, and More](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

 Posted on: August 5, 2024  [![Free Composting Services News Flash](images/3a4c4b02e52767ded72fb3ae0b008616d9ee71351144e097648c527b9047bf9f)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#composting) 

###  [Get Free Composting Services for Businesses](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#composting) 

 Posted on: August 5, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3abf78b) 

###  [Fall Activity Registration is Open, Redmond Lights, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3abf78b) 

 Posted on: July 31, 2024  [![SUN Bucks News Flash](images/3bed8ba3363dde81273b5945a452f7f3165cae09e17f96ab295ff595ae3633b4)](https://sunbucks.dshs.wa.gov/en) 

###  [Get Help for Summer Meals](https://sunbucks.dshs.wa.gov/en) 

 Posted on: July 29, 2024  [![ROW Feedback News Flash](images/f8023b422a036747acb0fb54e44f26a9677b328cc4a0ae7478aba6e58efb1627)](https://www.letsconnectredmond.com/row) 

###  [We Want Your Feedback](https://www.letsconnectredmond.com/row) 

 Posted on: July 29, 2024  [![Heat Pumps News Flash](images/e2e1e84b582d49a41758318f5d1020ee34205b8786b08febcd9806d9e2604b5f)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#heat-pumps) 

###  [Save Thousands on Heat Pumps](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#heat-pumps) 

 Posted on: July 29, 2024  [![Ride the Rails to Redmond News Flash](images/24f5c8877dd627b7ba1314ef9927575d968db2ef2ffca37cacbde7b84833425b)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#ride-the-rails) 

###  [Ride the Rails to Redmond](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#ride-the-rails) 

 Posted on: July 29, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3aa8c0a) 

###  [Register for Fall Activities, Free Life Jackets, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3aa8c0a) 

 Posted on: July 24, 2024  [![Parks, Trails, and Rec News Flash](images/dc4d42cbdf9d152488cffc5c2936d2a409d591a04ee18d0ff727481e447523f4)](https://www.redmond.gov/CivicAlerts.aspx?AID=2094) 

###  [Join Our Parks, Trails, and Recreation Commission](https://www.redmond.gov/CivicAlerts.aspx?AID=2094) 

 Posted on: July 22, 2024  [![Salary Commission News Flash](images/26e1558eca705a252faa02b1ea82e70af3f19d0eee79f0fcb08db3f424226d51)](https://www.redmond.gov/1972/Salary-Commission) 

###  [Join the Salary Commission](https://www.redmond.gov/1972/Salary-Commission) 

 Posted on: July 22, 2024  [![Ecomonic Development News Flash](images/585ca066b992ccf887b15b8b1d1f91965d5942baafc011413f13ed0b6832849c)](https://www.redmond.gov/322/Economic-Development) 

###  [View Redmond’s Economic Development Strategic Plan](https://www.redmond.gov/322/Economic-Development) 

 Posted on: July 22, 2024  [![Dog Pop Up News Flash](images/2c7082256cc2fb50f8df0f18af8ff3e8fd078f03acad70f0e71429c6eb85c9a2)](https://www.letsconnectredmond.com/dogpark) 

###  [Paws and Play in Redmond](https://www.letsconnectredmond.com/dogpark) 

 Posted on: July 22, 2024  [![Storm Water and Surface Water News Flash](images/29887546915c133ac27e3b69d84006ec64b68c7233ac42976e68f9a783082864)](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

###  [Share Your Feedback on Stormwater and Surface Water](https://www.letsconnectredmond.com/stormwater-surface-water-system-plan) 

 Posted on: July 22, 2024  [![Horatio Flowers FOCUS News Flash](images/327856c5e0cdebf2bf2cc4ce0342121ae15280857e9a6139bd559709d4837e7c)](https://www.redmond.gov/2158/Focus---Summer-2024#shining-light) 

###  [Update on the Lamp Posts Blooming in Overlake](https://www.redmond.gov/2158/Focus---Summer-2024#shining-light) 

 Posted on: July 22, 2024  [![Focus_Summer 2024_News Flash](images/30b689ac40f943e9715d7fb98d5e24210ecc117e462bca5582dc4997a9f0ab76)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#summer-camps) 

###  [Spend Your Summer in Redmond](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#summer-camps) 

 Posted on: July 15, 2024  [![civil service commissioner_News Flash](images/ff31bd8498e88b78341069716ec898ddcf9796da1f65b5251ea552ba3aa71193)](https://www.redmond.gov/1164/Civil-Service-Commission) 

###  [Volunteer to Help Redmond Public Safety](https://www.redmond.gov/1164/Civil-Service-Commission) 

 Posted on: July 15, 2024  [![Michael Plymouth Crossing_News Flash](images/94d4c5fa00796c695dc73d74bc6bb905cc3be3dbd108b15fe183d99d68382783)](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#connections) 

###  [Read About How Housing Builds Connections](https://www.redmond.gov/2158/Focus---Summer-2024?utm_medium=email&utm_source=govdelivery#connections) 

 Posted on: July 15, 2024 | Last Modified on: July 15, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a90e60) 

###  [Rockin' on the River, Derby Days Feedback, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a90e60) 

 Posted on: July 17, 2024  [![Parks and Rec Month News Flash](images/6a105219859e3261d72c3b97154ec701dd8c7d4f7d26bd765d6bfe1fc65cafe0)](https://www.redmond.gov/165/Parks-Recreation?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate National Parks and Recreation Month](https://www.redmond.gov/165/Parks-Recreation?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  [![Gardening Class News Flash](images/e5da3058a20ec6b097d04491c69abfb0da252d7c2ec6fc74e8f97885221fcdc4)](https://cascadewater.org/water-efficiency/cascade-gardener/?utm_medium=email&utm_source=govdelivery) 

###  [Join Free Cascade Gardener Tours and Classes](https://cascadewater.org/water-efficiency/cascade-gardener/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  [![Don't Wait to Inflate](images/f85bb15d2e43474493c4561246b75e5a9a92c2585f776a2c04b1f5a143a56fca)](https://www.pugetsoundstartshere.org/DontwaittoInflate/?utm_medium=email&utm_source=govdelivery) 

###  [Don’t Wait to Inflate](https://www.pugetsoundstartshere.org/DontwaittoInflate/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 8, 2024  ![Focus_Summer 2024_News Flash](images/30b689ac40f943e9715d7fb98d5e24210ecc117e462bca5582dc4997a9f0ab76)  

###  [Read the Latest Focus Newsletter](https://www.redmond.gov/CivicAlerts.aspx?AID=2076) 

 Posted on: July 3, 2024  [![Disability Pride Month](images/f8d5eacdb60ec8a1c6e7368a8d130c3a086d5deb4501749e211472dd9e564c47)](https://thearc.org/blog/why-and-how-to-celebrate-disability-pride-month/?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Disability Pride Month](https://thearc.org/blog/why-and-how-to-celebrate-disability-pride-month/?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 1, 2024  [![Right of Way Use Proposal](images/58d9dc5e715d5e3f6ac0e3fc3458bc5572fe323756f15b4a4eca15626eb56b75)](https://www.redmond.gov/2157/Proposed-Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Right-of-Way Use Fee Proposal](https://www.redmond.gov/2157/Proposed-Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

 Posted on: July 1, 2024  [![6-24 Take Me Home News Flash](images/faa35dc234809cb7d905616c4afdca202abb3cb89fc8f35a479ee11df09d55a1)](https://www.redmond.gov/2149/Take-Me-Home-Program?utm_medium=email&utm_source=govdelivery) 

###  [Register Your Loved One for Take Me Home](https://www.redmond.gov/2149/Take-Me-Home-Program?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Drink in Data Redmond Water News Flash](images/b9afe3301badb14bfa87aefef30ecb38987ee63b94fd7d7fa8f810587970268a)](https://www.redmond.gov/DocumentCenter/View/28402/2024-Water-Quality-Report?utm_medium=email&utm_source=govdelivery) 

###  [Drink in the Data for Redmond’s Water](https://www.redmond.gov/DocumentCenter/View/28402/2024-Water-Quality-Report?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Sewer Wastewater Plan News Flash](images/114dddd32bb6ff488c023148aaf1e871e4a23af1ce6e60c5c6e2b46a51cb1a2e)](https://www.letsconnectredmond.com/general-sewer-plan?utm_medium=email&utm_source=govdelivery) 

###  [Review the General Wastewater Plan](https://www.letsconnectredmond.com/general-sewer-plan?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Civil Council Commissioner News Flash](images/0518f1ff085a81eae77cba43fc7d865ba9c3f2bf7749a301e763bdeced3d9c68)](https://www.redmond.gov/CivicAlerts.aspx?AID=2034&utm_medium=email&utm_source=govdelivery) 

###  [Join the Civil Service Commission](https://www.redmond.gov/CivicAlerts.aspx?AID=2034&utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-24 Right of Way Fee News Flash](images/0857bab419fb5987b5ae0269a4e11a73e3a7ab5f3936b9317fba2119892f1b99)](https://www.redmond.gov/2157/Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

###  [Learn About New Right of Way Use Fees](https://www.redmond.gov/2157/Right-of-Way-Use-Fee?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 24, 2024  [![6-17_Here in Redmond_News Flash](images/d5dbd1020ec60fbd0c4966ced3c07d19678127dd379f2870e96f2e8d6830f264)](https://www.youtube.com/watch?feature=youtu.be&utm_medium=email&utm_source=govdelivery&v=NvECG33vsak) 

###  [Relish in the Dog Days of Summer](https://www.youtube.com/watch?feature=youtu.be&utm_medium=email&utm_source=govdelivery&v=NvECG33vsak) 

 Posted on: June 17, 2024 | Last Modified on: June 17, 2024  [![6-17_Eastside Energy_News Flash](images/7e34a4b7094ca30d514caf206a9477a573baa17cd0ec2cb7b0baac2bf305b12f)](https://www.energysmarteastside.org/?utm_medium=email&utm_source=govdelivery) 

###  [Making a Difference on the Eastside Through a Clean Energy Program](https://www.energysmarteastside.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024  [![6-17_Tourism_News Flash](images/6448975e2174bf83a72aa27cb0c8067393194a07f1ac955ab59ba6b60ef506d1)](https://www.redmond.gov/DocumentCenter/View/32918/Redmond-Tourism-Strategic-Plan-FINAL-DRAFT?utm_medium=email&utm_source=govdelivery) 

###  [View Redmond’s First Tourism Strategic Plan](https://www.redmond.gov/DocumentCenter/View/32918/Redmond-Tourism-Strategic-Plan-FINAL-DRAFT?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024  [![6-17_Be Kind to Birds, Bats, Butterflies, and Bees_News Flash](images/056b5f75f6693c8c52a90dd232cd8e19525ef3453d44ae122f35b9febd5a446d)](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg?utm_medium=email&utm_source=govdelivery) 

###  [Be Kind to Birds, Bats, Butterflies, and Bees](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 17, 2024 | Last Modified on: June 17, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a243dc) 

###  [Derby Days Music, Summer Radness, Busker Program, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3a243dc) 

 Posted on: June 12, 2024  [![6-10_enews_Pride_News Flash](images/9c84cd74b4d6dea832cb32a03e18c10a8b46008b9e58e0ec7dc173a193b8464f)](https://www.redmond.gov/DocumentCenter/View/32872/Pride-Proclamation-2024?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Pride Month](https://www.redmond.gov/DocumentCenter/View/32872/Pride-Proclamation-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![6-10_enews_OVerlake Passport Challenge_News Flash](images/9418d862e2e04aeb4e1221225f67db62e9022d11677785555f7a74c3f2056000)](https://experienceredmond.com/Overlake-Passport-Challenge/?utm_medium=email&utm_source=govdelivery) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport-Challenge/?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![6-10_enews_Marymoor Park_News Flash](images/f5ce40b9515b29f640e77c4c548630036e972cbab01f6b0d44451024d5455f4c)](https://survey123.arcgis.com/share/2ff9323500694fe494b4b8d1b79e3812?utm_medium=email&utm_source=govdelivery) 

###  [Help Improve Marymoor Park](https://survey123.arcgis.com/share/2ff9323500694fe494b4b8d1b79e3812?utm_medium=email&utm_source=govdelivery) 

 Posted on: June 10, 2024  [![5-20_enews_EMS Week_News Flash](images/bbd8d2eb6ebc42e6fc426e6fb4607cb6930a0f9db297c82ef77c19cc21ea2ac6)](https://emsweek.org/?utm_medium=email&utm_source=govdelivery) 

###  [Join Us in Honoring Emergency Medical Services Week](https://emsweek.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Public Works Week_News Flash](images/467e9fde44ab66e445636461330865bf99f6d3d2500e6626712b6230963b8a57)](https://www.redmond.gov/1772/National-Public-Works-Week?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate National Public Works Week](https://www.redmond.gov/1772/National-Public-Works-Week?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Community Champions Award_News Flash](images/ce6168a913dc0a5d59c04db854eb8c46139360a36c86b59f9211e212c899725c)](https://www.redmond.gov/CivicAlerts.aspx?AID=2007&utm_medium=email&utm_source=govdelivery) 

###  [Redmond Earns Community Champion Award](https://www.redmond.gov/CivicAlerts.aspx?AID=2007&utm_medium=email&utm_source=govdelivery) 

 Posted on: May 20, 2024  [![5-20_enews_Startup and Small Business Meeting_News Flash](images/549d13e276dd284f68c06ecc3f16c20f565183a094670db9f0a9cdd898dc7c45)](https://www.startup425.org/event-details/startup-small-business-coworking-redmond-may-2024?utm_medium=email&utm_source=govdelivery) 

###  [Attend a Startup and Small Business Coworking Event](https://www.redmond.gov/CivicAlerts.aspx?AID=2009) 

 Posted on: May 20, 2024  [![5-13_enews_RSCC Now Open_News Flash](images/88bfcf26474e054a1102dee228e1b1207b06a6669f8415f26080069daee1901e)](https://www.youtube.com/watch?v=wSgFDsBoyB0) 

###  [Enjoy the New Redmond Senior & Community Center](https://www.redmond.gov/CivicAlerts.aspx?AID=2006) 

 Posted on: May 13, 2024  [![5-13_enews_AANHPI Month_News Flash](images/2ae857cd2a6c8a79060919536e15fb4f1cb7b2e23dfc1f9d0416f4ce501b0423)](https://www.redmond.gov/DocumentCenter/View/32594/2024-AANHPI-Heritage-Month-Proclamation) 

###  [Celebrate Asian American, Native Hawaiian, and Pacific Islander Heritage Month](https://www.redmond.gov/CivicAlerts.aspx?AID=2005) 

 Posted on: May 13, 2024  ![5-13_enews_National Police Week_News Flash](images/6e7ae85e78b975229fe5b8f7b546eacce05a84724470e84d19b2b4c0c0f7b346)  

###  [Honoring National Police Week](https://www.redmond.gov/CivicAlerts.aspx?AID=2004) 

 Posted on: May 13, 2024  [![5-13_enews_Affordable Housing Week_News Flash](images/1d669f835441b06cdfb74435ac1d8296a0b3e81e9598862071580e5ebeefe2ef)](https://www.housingconsortium.org/affordable-housing-week/?eType=EmailBlastContent&eId=40aade70-b1a0-46e5-9d6b-c9289a042db6) 

###  [Learn About Affordable Housing Week](https://www.redmond.gov/CivicAlerts.aspx?AID=2003) 

 Posted on: May 13, 2024  [![5-13_enews_Overlake Passport Challenge_News Flash](images/89013d353420535d46c7da4959ba82979ca845da42e6a002033b3cecb2b4106c)](https://experienceredmond.com/Overlake-Passport-Challenge) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport-Challenge) 

 Posted on: May 13, 2024  [![5-13_enews_Community Van_News Flash](images/0208faf1498a02739f6bb7772661428f04dbd70ecd41327f0cbdd5b06dd7b48f)](https://www.goredmond.com/redmond-community-van) 

###  [Take a Ride in a Community Van](https://www.goredmond.com/redmond-community-van) 

 Posted on: May 13, 2024  [![5-13_enews_Sustainable Vegetaion Management_News Flash](images/ead6b945719b158d4fbba021265db65ebc406061baeaa732c64f443447a5b9ba)](https://www.redmond.gov/953/Climate-Resiliency-Sustainability-in-Veg) 

###  [Learn About the City’s Commitment to Environmental Stewardship](https://www.redmond.gov/CivicAlerts.aspx?AID=2000) 

 Posted on: May 13, 2024  [![5-6_enews_Older Americans Month_News Flash](images/3c99da3172531c7e0bc4bb9587d7fd15a8916c8fcf752c08e790ecd3241046af)](https://www.redmond.gov/DocumentCenter/View/32591/Older-Americans-Month-Proclamation---May-2024?utm_medium=email&utm_source=govdelivery) 

###  [Honoring Older Americans Month](https://www.redmond.gov/DocumentCenter/View/32591/Older-Americans-Month-Proclamation---May-2024?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Bike Everywhere Day_News Flash](images/d457ff0dd4a9efcb05394ffd36bd7df83589f4bf7e923b3536d247a49901e377)](https://cityofredmond.maps.arcgis.com/apps/instant/basic/index.html?47.667=&appid=659e8920e5de4bb3867c577a1a770c9e&center=-122.1201&hiddenLayers=18f0bf745dc-layer-20&level=12&utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Bike Everywhere Month](https://cityofredmond.maps.arcgis.com/apps/instant/basic/index.html?47.667=&appid=659e8920e5de4bb3867c577a1a770c9e&center=-122.1201&hiddenLayers=18f0bf745dc-layer-20&level=12&utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Walking Tour_News Flash](images/4f35f6a1090cc372d2147befe402982f19857f7a242eb21f293ef537e4525682)](https://www.letsconnectredmond.com/safe-streets-for-all?utm_medium=email&utm_source=govdelivery) 

###  [Help Make Roads Safer](https://www.redmond.gov/CivicAlerts.aspx?AID=1994) 

 Posted on: May 7, 2024  [![5-6_enews_Clean Drinking Water_News Flash](images/eadef2a0cff8a84db4fe3952b6b81d6b5ba8c5d4afff59b51b758dc9e2482294)](https://www.redmond.gov/1834/Drinking-Water-Operations?utm_medium=email&utm_source=govdelivery) 

###  [Celebrate Clean Drinking Water](https://www.redmond.gov/1834/Drinking-Water-Operations?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![5-6_enews_Clean Streams_News Flash](images/a2d226acf2b09151cb87a7930b0ad926a9cf52f70fc5e03cfd004c81d0706a84)](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#neighborhood) 

###  [Keep Our Streams Clean](https://www.redmond.gov/1225/Taking-Action?utm_medium=email&utm_source=govdelivery#neighborhood) 

 Posted on: May 7, 2024  [![5-6_enews_Migratory Birds_News Flash](images/78888f5c6d2b970d1a0035bac5787f5140946aca46e280b73330d31f37ce6db6)](https://www.migratorybirdday.org/?utm_medium=email&utm_source=govdelivery) 

###  [Protect Insects to Protect Birds](https://www.migratorybirdday.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: May 7, 2024  [![4-29_enews_RSCC Grand Opening copy](images/437d57bceee1ed34edd8ab12b00c3625a969ab5b8d48176d95a119e6336df4bb)](https://www.redmond.gov/1867/Redmond-Senior-Community-Center?utm_medium=email&utm_source=govdelivery) 

###  [Join Us for the Redmond Senior & Community Center Grand Opening](https://www.redmond.gov/1867/Redmond-Senior-Community-Center?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Municipal Campus Parking copy](images/e54c278ceabbdeb7e36ad6602b1103c6c40862055903e5111d8796c45f240795)](https://www.redmond.gov/2124?utm_medium=email&utm_source=govdelivery) 

###  [Stay Informed About Municipal Campus Parking Changes](https://www.redmond.gov/2124?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Overlake Passport copy](images/4c17dbc847a772881ae65031871d4b6d6021098f4b885e767005c086c9e7c1a9)](https://experienceredmond.com/Overlake-Passport Challenge/?utm_medium=email&utm_source=govdelivery) 

###  [Explore the Overlake Neighborhood with Redmond's New Overlake Passport Challenge](https://experienceredmond.com/Overlake-Passport Challenge/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Light the Night Red copy](images/0c96d791a380c9851e8f8fcfd8b5de8f174beb2c22758d21d59df4ea895f5ffa)](https://weekend.firehero.org/events/memorial-weekend/light-night-fallen-firefighters/?utm_medium=email&utm_source=govdelivery) 

###  [Light the Night to Honor Fallen Firefighters](https://weekend.firehero.org/events/memorial-weekend/light-night-fallen-firefighters/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Prepare for Wildfires copy](images/3b75a9aee367bec032675df43be036b38ac78195e1a42cfc8d54424b07b1f637)](https://www.nfpa.org/Events/Events/National-Wildfire-Community-Preparedness-Day?utm_medium=email&utm_source=govdelivery) 

###  [Keep Your Home Safe this Wildfire Season](https://www.nfpa.org/Events/Events/National-Wildfire-Community-Preparedness-Day?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 29, 2024  [![4-29_enews_Summer Planning Academy copy](images/1ce78f658abf9860c040a7c8316d664867237fdce94ddc13d7ad7ca492e015f8)](https://www.psrc.org/get-involved/summer-planning-academy?utm_medium=email&utm_source=govdelivery) 

###  [Apply for the Regional Summer Planning Academy](https://www.redmond.gov/CivicAlerts.aspx?AID=1952) 

 Posted on: April 29, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39877bd) 

###  [Grand Opening of the New Redmond Senior & Community Center, Art Walk Muralists, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39877bd) 

 Posted on: April 24, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/396fb66) 

###  [Earth Day with Green Redmond, Community Paint Day, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/396fb66) 

 Posted on: April 17, 2024  [![4-15_enews_Work Zone Awareness_News Flash](images/fdfa34d74f34a6cc73535fb6fb1151035519b5cfedfe161f1bc47b3e518082bf)](https://wsdot.wa.gov/travel/traffic-safety-methods/work-zone-safety?utm_medium=email&utm_source=govdelivery) 

###  [Slow Down for National Work Zone Awareness Week](https://wsdot.wa.gov/travel/traffic-safety-methods/work-zone-safety?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_RSCC Parking_News Flash](images/aebcfe4a577a927f6fa44a1c84a730b73a133adb118da0078a4b863bbb623f0d)](https://www.redmond.gov/2124/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Senior & Community Center and Municipal Campus Parking](https://www.redmond.gov/2124/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Do Gooder Scholarship_News Flash](images/dd8632cf2b1ab69beec1f87ad2b719a5f2c8781f5b1c9267b2ec2e5853e09a9c)](https://www.redmond.gov/1412/Derby-Do-Gooder-Scholarship?utm_medium=email&utm_source=govdelivery) 

###  [Apply for Redmond’s Derby Days Do-Gooder Scholarship](https://www.redmond.gov/1412/Derby-Do-Gooder-Scholarship?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Demographics_News Flash](images/8917eff3b4d5442d8a42f25f9748752a4b215c72c6d912be6582aeb8af611a3e)](https://www.redmond.gov/818/Demographics-and-Statistics?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Demographics](https://www.redmond.gov/818/Demographics-and-Statistics?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![4-15_enews_Zoning Updates_News Flash](images/130e2858d06b79c6cad349c9025e0213294c14826a4d07ce7769e6b58a7cfd5a)](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

###  [Learn How Our Community is Changing](https://www.redmond.gov/1427/Redmond-2050?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 17, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39555e4) 

###  [Be Part of Derby Days, Scholarship for High School Seniors, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/39555e4) 

 Posted on: April 10, 2024  [![Parks & Rec eNews](images/9703425efd3c61d5f215cd94e1cfd0a09bc759fd91cc87bdc1d19c3fa377eead)](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3942b8a) 

###  [Pop-up Dog Parks Opening, Earth Day Activities, and More!](https://content.govdelivery.com/accounts/WAREDMOND/bulletins/3942b8a) 

 Posted on: April 5, 2024  [![4-1_enews_Earth Month_News Flash](images/af92995c535b3577a3ff105d858dd12bc7810f4508bd818f9da8b96b7808dcdc)](https://www.redmond.gov/1725/Earth-Month) 

###  [Celebrate Earth Month](https://www.redmond.gov/1725/Earth-Month) 

 Posted on: April 1, 2024  [![4-1_enews_Natural Yard Care_News Flash](images/1fcd349beca56cc498ba37a448e782aaaeefb2dd714eeb305004c29bb9d5ef81)](https://www.naturalyardcare.org/?utm_medium=email&utm_source=govdelivery) 

###  [Grow Healthy Natural Yards](https://www.naturalyardcare.org/?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_RSCC Parking_News Flash](images/d38ec050e83bf6ae1012567638762aa45264a1ba786d9d55bc96e1bef5196433)](https://www.redmond.gov/2124/32981/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

###  [Learn About Redmond Senior & Community Center and Municipal Campus Parking](https://www.redmond.gov/2124/32981/Municipal-Campus-Parking?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Sexual Assault Awareness Month_News Flash](images/d88fd54e27fe72359225c34826a56252561e8a212afbfc13cad1edb673a66881)](https://www.redmond.gov/DocumentCenter/View/32202/Sexual-Assault-Awareness-Month-2024-Proclamation?utm_medium=email&utm_source=govdelivery) 

###  [Recognizing Sexual Assault Awareness Month](https://www.redmond.gov/DocumentCenter/View/32202/Sexual-Assault-Awareness-Month-2024-Proclamation?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Volunteer Month_News Flash](images/ff59dc5bef0d910deee43ef5851f41aa20ceaa13f87da57fff682e1858093c04)](https://www.redmond.gov/661/Volunteer-Opportunities?utm_medium=email&utm_source=govdelivery) 

###  [Participate in National Volunteer Month](https://www.redmond.gov/661/Volunteer-Opportunities?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024  [![4-1_enews_Donate Blood_News Flash](images/3ba6798e9a0604dacc326edcf73341d4e5d27777cf479bebafc22e147bed8fb1)](https://donate.bloodworksnw.org/donor/schedules/sponsor_code?utm_medium=email&utm_source=govdelivery) 

###  [Save a Life by Donating Blood](https://donate.bloodworksnw.org/donor/schedules/sponsor_code?utm_medium=email&utm_source=govdelivery) 

 Posted on: April 1, 2024 <script type="text/javascript" language="javascript"><!--function redrawContent(closeModal) {raiseAsyncPostback('ctl00_ctl00_MainContent_ModuleContent_ctl00_contentUpdatePanel', '', closeModal);}$(document).ready(function () {if (!window.isResponsiveEnabled) { $('div.moduleContentNew').addClass('minWidth320px');}var color = $("div.moduleContentNew").css("color") + " !important";var style = $('<style>span.arrow { color:' + color + '; }</style>');$('html > head').append(style);});function pageLoad() {$('#newsSortBy').bind('change', function () { var url = $(this).val(); if (url) { window.location = url; } return false;});}//--></script> <script type="text/javascript">order+='ModuleContent\n'</script> 

### Live Edit

 [](https://www.redmond.gov/CivicAlerts.aspx?AID=2239)  <script type="text/javascript">//<![CDATA[Sys.Application.add_init(function() { $create(AjaxControlToolkit.ModalPopupBehavior, {"BackgroundCssClass":"modalBackground","CancelControlID":"ctl00_LiveEditCloseButton","PopupControlID":"ctl00_ctl00_MainContent_ctl00_liveEditPopupWindow","PopupDragHandleControlID":"ctl00_liveEditTitleBar","dynamicServicePath":"/CivicAlerts.aspx","id":"editItemBehavior"}, null, null, $get("ctl00_ctl00_MainContent_ctl00_liveEditSpawnWindow"));});//]]></script> 

###  [Popular](https://www.redmond.gov/QuickLinks.aspx?CID=105) 

 1.  [Home](https://www.redmond.gov/CivicAlerts.aspx?AID=2239)  
 1.  [Events](https://www.redmond.gov/294)  
 1.  [Jobs](https://www.governmentjobs.com/careers/redmondwa)  
 1.  [Recreation Activities](https://www.redmond.gov/184/Activities)  
 /QuickLinks.aspx 

###  [Find](https://www.redmond.gov/QuickLinks.aspx?CID=106) 

 1.  [City Council](https://www.redmond.gov/189)  
 1.  [Parks & Trails](https://www.redmond.gov/186)  
 1.  [Permits](https://www.redmond.gov/898)  
 1.  [Transportation](https://www.redmond.gov/221)  
 /QuickLinks.aspx 

###  [Report / Request](https://www.redmond.gov/QuickLinks.aspx?CID=107) 

 1.  [Report an Issue](https://redmondwa.qscend.com/311)  
 1.  [Request a Service](https://redmondwa.qscend.com/311)  
 1.  [Public Record](https://www.redmond.gov/777)  
 1.  [Police Record](https://www.redmond.gov/698)  
 /QuickLinks.aspx 

###  [Helpful Links](https://www.redmond.gov/QuickLinks.aspx?CID=108) 

 1.  [ADA Program](https://www.redmond.gov/871)  
 1.  [Title VI](https://www.redmond.gov/857)  
 1.  [Website Accessibility](https://www.redmond.gov/873/5722/Web-Accessibility)  
 1.  [Website Policies](https://www.redmond.gov/385)  
 /QuickLinks.aspx 

### Social Media

  [Facebook](https://www.redmond.gov/facebook)   [X](https://www.redmond.gov/twitter)   [Instagram](https://www.redmond.gov/instagram)   [YouTube](https://www.redmond.gov/youtube)  

### Sign Up For Our Newsletter

 1. 
 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvca56cd53-4ad3-45f7-9522-a35eb6c948a8.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1.    

 ![Redmond Washington Homepage](images/033f075b6331f4a5b7122ab61000f19ec11e27957fcbf85a84a641bfc3d64e68)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvce94195d-0d21-4a69-9b41-22564e582b93.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1. Phone:  [425-556-2900](tel:425-556-2900) 

 1.  [15670 NE 85th Street](https://goo.gl/maps/CJcLDqJFWRpxZxbL6) 

 1. P.O. Box 97010

 1.  [Redmond, WA 98073-9710](https://goo.gl/maps/CJcLDqJFWRpxZxbL6) 
 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdv97860bf2-90f8-4398-876c-7ac5e8181ba3.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

 1.  [Contact Us](https://www.redmond.gov/directory)  

 1.  [Site Map](https://www.redmond.gov/sitemap)  

 1.  [Website Feedback](https://www.redmond.gov/FormCenter/Communications-12/Website-Feedback-87)  
 /QuickLinks.aspx Loading Loading Do Not Show AgainClose <script src="/Assets/Scripts/APIClient.js"></script><script src="/Assets/Mystique/Shared/Scripts/Moment/Moment.min.js"></script><script src="/Assets/Scripts/SplashModal/SplashModalRender.js"></script><script> $(document).ready(function () { var filter = { targetId: '', targetType: 0 } new SplashModalRender().triggerRender(filter); });</script><script src="/-1135462429.js" type="text/javascript"></script><script>document.addEventListener("DOMContentLoaded", () => { const getValueTS = (elem, attr) => { const val = window.getComputedStyle(elem)[attr]; return val? parseInt(val, 10) : undefined; }; const clampTS = (number, min, max) => Math.min(Math.max(number, min), max); const isPageEditingTS = () => { return document.querySelector("#doneEditing") !== null || typeof DesignCenter !== "undefined"; }; const isTransparentTS = (elem) => { const bg = window.getComputedStyle(elem)['background-color']; const bgColorRegexTS = /rgba\((\d+), (\d+), (\d+), (\d*\.?\d*)\)/; const matchState = bg.match(bgColorRegexTS); if (!matchState || matchState.length !== 5) return false; const alpha = parseFloat(matchState[4], 10); return alpha >= 0 && alpha < 1; }; const iterateLeftPads = (callback) => { const containersTS = document.querySelectorAll("[class^='siteWrap'],[class*=' siteWrap']"); containersTS.forEach(containerTS => { if (containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-leftpad') === null) { callback(containerTS); } }); }; const iterateRightPads = (callback) => { const containersTS = document.querySelectorAll("[class^='siteWrap'],[class*=' siteWrap']"); containersTS.forEach(containerTS => { if (containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-rightpad') === null) { callback(containerTS); } }); }; const anchor = document.getElementById("divToolbars"); const bodyWrapper = document.getElementById("bodyWrapper"); const outerSizingTS = document.getElementById("bannerContainerTS"); const innerSizingTS = document.getElementById("bannerSizingTS"); const bodyContainerTS = document.getElementById("bodyContainerTS"); const headerContainerTS = document.getElementById("headerContainerTS"); const fixedTopTS = document.querySelector(".fixedTopTS"); const fixedBottomTS = document.querySelector(".fixedBottomTS"); const fixedLeftTS = document.querySelector(".fixedLeftTS"); const fixedRightTS = document.querySelector(".fixedRightTS"); let initialTopTS; let topAttachTS; if (fixedTopTS) { initialTopTS = getValueTS(fixedTopTS, 'top'); const attachment = fixedTopTS.getAttribute('data-attach'); if (attachment) topAttachTS = document.getElementById(attachment); } const resizeAdjustmentTS = () => { const editing = isPageEditingTS(); const anchorStyle = getComputedStyle(anchor); const anchorPaddingTop = parseInt(anchorStyle.paddingTop, 10); // console.log("Padding Top:", anchorPaddingTop);  // Sticky Top Adjustment if (fixedTopTS) { if (editing) { fixedTopTS.classList.add("forceUnfixTS"); } else { fixedTopTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedTopTS).position === "sticky") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; fixedTopTS.style.top = `${anchorHeight + initialTopTS}px`; bodyWrapper.style.paddingTop = `${anchorHeight - anchorPaddingTop}px`; if (isTransparentTS(fixedTopTS)) { innerSizingTS.style.paddingTop = `${initialTopTS + fixedTopTS.offsetHeight - 1}px`; outerSizingTS.style.paddingTop = ""; } else { outerSizingTS.style.paddingTop = ""; innerSizingTS.style.paddingTop = ""; } } else { const mobileMenu = document.getElementById("nav-open-btn"); const mobileMenuHeight = mobileMenu? mobileMenu.offsetHeight : 0; fixedTopTS.style.top = ""; bodyWrapper.style.paddingTop = `${anchor.offsetHeight + mobileMenuHeight - anchorPaddingTop}px`; } } // Sticky Bottom Adjustment if (fixedBottomTS) { if (editing || fixedBottomTS.offsetHeight > 200) { fixedBottomTS.classList.add("forceUnfixTS"); } else { fixedBottomTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedBottomTS).position === "fixed") { bodyContainerTS.style.paddingBottom = `${fixedBottomTS.offsetHeight}px`; bodyWrapper.style.paddingTop = `${anchor.offsetHeight - anchorPaddingTop}px`; } else { bodyContainerTS.style.paddingBottom = ""; bodyWrapper.style.paddingTop = `${anchor.offsetHeight - anchorPaddingTop}px`; } } // Fixed Left Adjustment if (fixedLeftTS) { if (editing) { fixedLeftTS.classList.add("forceUnfixTS"); } else { fixedLeftTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedLeftTS).position === "fixed") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; const headerHeight = headerContainerTS.offsetHeight - 1; fixedLeftTS.style.top = `${anchorHeight + headerHeight + 100}px`; const leftBoundingTS = fixedLeftTS.getBoundingClientRect(); iterateLeftPads(containerTS => { const containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= leftBoundingTS.right) { containerTS.style.paddingLeft = `${leftBoundingTS.width + 16}px`; } }); } } // Fixed Right Adjustment if (fixedRightTS) { if (editing) { fixedRightTS.classList.add("forceUnfixTS"); } else { fixedRightTS.classList.remove("forceUnfixTS"); } if (getComputedStyle(fixedRightTS).position === "fixed") { const anchorHeight = anchor? anchor.offsetHeight - 1 : 0; const headerHeight = headerContainerTS.offsetHeight - 1; fixedRightTS.style.top = `${anchorHeight + headerHeight + 100}px`; const rightBoundingTS = fixedRightTS.getBoundingClientRect(); iterateRightPads(containerTS => { const containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= rightBoundingTS.right) { containerTS.style.paddingRight = `${rightBoundingTS.width + 16}px`; } }); } } }; const scrollAdjustmentTS = () => { if (!fixedTopTS || !topAttachTS) return; const topPosition = getComputedStyle(fixedTopTS).position; if (topPosition === "sticky" || topPosition === "absolute") { const anchorBounding = anchor.getBoundingClientRect(); const attachBounding = topAttachTS.getBoundingClientRect(); fixedTopTS.style.top = `${Math.max(anchorBounding.bottom - 1, attachBounding.bottom)}px`; } else { fixedTopTS.style.top = `${initialTopTS}px`; } }; // Event Listeners for Scroll and Resize window.addEventListener("scroll", scrollAdjustmentTS); window.addEventListener("resize", () => { clearTimeout(this.adjustTimeout); this.adjustTimeout = setTimeout(resizeAdjustmentTS, 350); }); // Initial adjustment on page load resizeAdjustmentTS(); });</script><script>if (document.location.pathname == "/list.aspx") { const urlParams = new URLSearchParams(window.location.search); const theEmail = urlParams.get('email'); if (theEmail) { $("#emailAddressSignIn").val(theEmail); signIn(); }}</script><script>$(document).ready(function() { // Preload Images for Graphic Buttons.5 seconds after page loads var waitToPreload = 500; // Parse through the styles on the page, finding any image URLs $($("style").text().match(/url\s*\('?\/?(?:[^/]+\/)*?([^/:]+)'?\)/g)).each(function() { var url = this.replace("url(","").replace(")","").replaceAll("'","").replaceAll('"',""); setTimeout(preloadImage, waitToPreload, url); }); function preloadImage(url) { var image = $("<img />"); $(image).attr('src',url).appendTo('body').hide(); }});</script><script src="//cdn.loop11.com/embed.js" type="text/javascript" async="async"></script><script type="text/javascript">/*<![CDATA[*/(function() {var sz = document.createElement('script'); sz.type = 'text/javascript'; sz.async = true;sz.src = '//siteimproveanalytics.com/js/siteanalyze_6745.js';var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(sz, s);})();/*]]>*/</script><script type="text/javascript"> window._monsido = window._monsido || { token: "gUHJ1NzC3wpOQrmj03jgIg", statistics: { enabled: true, cookieLessTracking: false, documentTracking: { enabled: true, documentCls: "monsido_download", documentIgnoreCls: "monsido_ignore_download", documentExt: [], }, }, heatmap: { enabled: true, }, pageAssistV2: { enabled: true, theme: "light", mainColor: "#783CE2", textColor: "#ffffff", linkColor: "#783CE2", buttonHoverColor: "#783CE2", mainDarkColor: "#052942", textDarkColor: "#ffffff", linkColorDark: "#FFCF4B", buttonHoverDarkColor: "#FFCF4B", greeting: "Discover your personalization options", direction: "leftbottom", coordinates: "undefined undefined undefined undefined", iconShape: "circle", title: "Personalization Options", titleText: "Welcome to PageAssist™ toolbar! Adjust the options below to cater the website to your accessibility needs.", iconPictureUrl: "logo", logoPictureUrl: "", logoPictureBase64: "", languages: [""], defaultLanguage: "", skipTo: false, alwaysOnTop: false,hotkeyEnabled: false }, };</script><script type="text/javascript" async src="https://app-script.monsido.com/v2/monsido-script.js"></script><script> (function () { const minWidth = 220; const maxWidth = 500; // Facebook widget will not expand past 500 function clamp__TS(num, min, max) { return Math.min(Math.max(num, min), max); } function adjustFacebookContainers__TS() { const iframes = document.querySelectorAll('iframe[src*="facebook.com"]'); iframes.forEach(iframe => { if (!iframe.parentElement.classList.contains('facebook-container')) { const container = document.createElement('div'); container.classList.add('facebook-container'); iframe.parentNode.insertBefore(container, iframe); container.appendChild(iframe); } adjustContainer__TS(iframe.parentElement); }); } function adjustContainer__TS(container) { const frame = container.querySelector('iframe'); if (!frame) { console.warn("No facebook widget found..."); return; } const containerWidth = container.clientWidth; const newWidth = clamp__TS(containerWidth, minWidth, maxWidth); // Use jQuery to manipulate the iframe's src and dimensions const src = new URL(frame.getAttribute("src")); src.searchParams.set("width", newWidth); frame.setAttribute("src", src); frame.setAttribute("width", newWidth); } window.addEventListener('load', adjustFacebookContainers__TS); window.addEventListener('resize', adjustFacebookContainers__TS); })();</script><script> function moveBannerToOuterWrap() { if ($(".fixedBannerTS #bannerDivbanner2").length) { $(".fixedBannerTS #bannerDivbanner2").appendTo("#outer-wrap"); } else { setTimeout(function () { moveBannerToOuterWrap(); }, 500); } } moveBannerToOuterWrap();</script> <script> function googleTranslateElementInit() { new google.translate.TranslateElement({ pageLanguage: "en" }, "google_translate_element"); // begin accessibility compliance $('img.goog-te-gadget-icon').attr('alt','Google Translate'); $('div#goog-gt-tt div.logo img').attr('alt','translate'); $('div#goog-gt-tt.original-text').css('text-align','left'); $('.goog-te-gadget-simple.goog-te-menu-value span').css('color','#000000'); $('.goog-te-combo').attr('aria-label','google translate languages'); $('svg.goog-te-spinner').attr('title','Google Translate Spinner'); $('.goog-te-gadget-simple.goog-te-menu-value span').css('color','#000000'); } $(function() { $.getScript("//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"); });</script><script type="text/javascript"> $(function () { document.cookie = "responsiveGhost=0; path=/"; }); $(window).on("load", function () { $('body').addClass('doneLoading').removeClass('hideContent'); if ($('#404Content').length > 0) $('div#bodyWrapper').css('padding', '0px'); }); </script> <script type="text/javascript">loadCSS('//fonts.googleapis.com/css?family=Lato:300,300italic,700,700italic,900,900italic,italic,regular|Libre+Baskerville:700,italic,regular|Roboto:700,900|Roboto+Condensed:700|Roboto+Slab:700|');</script> [{"WidgetSkinID":56,"ComponentType":0,"FontFamily":"","FontVariant":"","FontColor":"","FontSize":0.00,"FontStyle":0,"TextAlignment":0,"ShadowColor":"","ShadowBlurRadius":0,"ShadowSpreadRadius":0,"ShadowOffsetX":0,"ShadowOffsetY":0,"ShadowInset":false,"ShadowColor2":"","ShadowBlurRadius2":0,"ShadowSpreadRadius2":0,"ShadowOffsetX2":0,"ShadowOffsetY2":0,"ShadowInset2":false,"ShadowColor3":"","ShadowBlurRadius3":0,"ShadowSpreadRadius3":0,"ShadowOffsetX3":0,"ShadowOffsetY3":0,"ShadowInset3":false,"ShadowColor4":"","ShadowBlurRadius4":0,"ShadowSpreadRadius4":0,"ShadowOffsetX4":0,"ShadowOffsetY4":0,"ShadowInset4":false,"ShadowColor5":"","ShadowBlurRadius5":0,"ShadowSpreadRadius5":0,"ShadowOffsetX5":0,"ShadowOffsetY5":0,"ShadowInset5":false,"Capitalization":0,"HeaderMiscellaneousStyles1":"","HeaderMiscellaneousStyles2":"","HeaderMiscellaneousStyles3":"","BulletStyle":0,"BulletWidth":2.00,"BulletColor":"","LinkNormalColor":"","LinkNormalUnderlined":false,"LinkNormalMiscellaneousStyles":"","LinkVisitedColor":"","LinkVisitedMiscellaneousStyles":"","LinkHoverColor":"","LinkHoverUnderlined":false,"LinkHoverMiscellaneousStyles":"","LinkSelectedUnderlined":false,"ForceReadOnLinkToNewLine":false,"DisplayColumnSeparator":false,"ColumnSeparatorWidth":0.0000,"HoverBackgroundColor":"","HoverBackgroundGradientStartingColor":"","HoverBackgroundGradientEndingColor":"","HoverBackgroundGradientDirection":0,"HoverBackgroundGradientDegrees":0.0000000,"HoverBackgroundImageFileName":"","HoverBackgroundImagePositionXUseKeyword":true,"HoverBackgroundImagePositionXKeyword":0,"HoverBackgroundImagePositionX":{"Value":0.0000,"Unit":0},"HoverBackgroundImagePositionYUseKeyword":true,"HoverBackgroundImagePositionYKeyword":0,"HoverBackgroundImagePositionY":{"Value":0.0000,"Unit":0},"HoverBackgroundImageRepeat":0,"HoverBorderStyle":0,"HoverBorderWidth":0,"HoverBorderColor":"","HoverBorderSides":15,"HoverBorderRadiusTopLeft":{"Value":null,"Unit":1},"HoverBorderRadiusTopRight":{"Value":null,"Unit":1},"HoverBorderRadiusBottomRight":{"Value":null,"Unit":1},"HoverBorderRadiusBottomLeft":{"Value":null,"Unit":1},"SelectedBackgroundColor":"","SelectedBackgroundGradientStartingColor":"","SelectedBackgroundGradientEndingColor":"","SelectedBackgroundGradientDirection":0,"SelectedBackgroundGradientDegrees":0.0000000,"SelectedBackgroundImageFileName":"","SelectedBackgroundImagePositionXUseKeyword":true,"SelectedBackgroundImagePositionXKeyword":0,"SelectedBackgroundImagePositionX":{"Value":0.0000,"Unit":0},"SelectedBackgroundImagePositionYUseKeyword":true,"SelectedBackgroundImagePositionYKeyword":0,"SelectedBackgroundImagePositionY":{"Value":0.0000,"Unit":0},"SelectedBackgroundImageRepeat":0,"SelectedBorderStyle":0,"SelectedBorderWidth":0,"SelectedBorderColor":"","SelectedBorderSides":15,"SelectedBorderRadiusTopLeft":{"Value":null,"Unit":1},"SelectedBorderRadiusTopRight":{"Value":null,"Unit":1},"SelectedBorderRadiusBottomRight":{"Value":null,"Unit":1},"SelectedBorderRadiusBottomLeft":{"Value":null,"Unit":1},"HoverFontFamily":"","HoverFontVariant":"","HoverFontColor":"","HoverFontSize":0.00,"HoverFontStyle":0,"HoverTextAlignment":0,"HoverShadowColor":"","HoverShadowBlurRadius":0,"HoverShadowSpreadRadius":0,"HoverShadowOffsetX":0,"HoverShadowOffsetY":0,"HoverShadowInset":false,"HoverShadowColor2":"","HoverShadowBlurRadius2":0,"HoverShadowSpreadRadius2":0,"HoverShadowOffsetX2":0,"HoverShadowOffsetY2":0,"HoverShadowInset2":false,"HoverShadowColor3":"","HoverShadowBlurRadius3":0,"HoverShadowSpreadRadius3":0,"HoverShadowOffsetX3":0,"HoverShadowOffsetY3":0,"HoverShadowInset3":false,"HoverShadowColor4":"","HoverShadowBlurRadius4":0,"HoverShadowSpreadRadius4":0,"HoverShadowOffsetX4":0,"HoverShadowOffsetY4":0,"HoverShadowInset4":false,"HoverShadowColor5":"","HoverShadowBlurRadius5":0,"HoverShadowSpreadRadius5":0,"HoverShadowOffsetX5":0,"HoverShadowOffsetY5":0,"HoverShadowInset5":false,"HoverCapitalization":0,"SelectedFontFamily":"","SelectedFontVariant":"","SelectedFontColor":"","SelectedFontSize":0.00,"SelectedFontStyle":0,"SelectedShadowColor":"","SelectedShadowBlurRadius":0,"SelectedShadowSpreadRadius":0,"SelectedShadowOffsetX":0,"SelectedShadowOffsetY":0,"SelectedShadowInset":false,"SpaceBetweenTabs":0,"SpaceBetweenTabsUnits":"","Trigger":4,"AnimationId":"00000000-0000-0000-0000-000000000000","AnimationClass":"animation00000000000000000000000000000000","ScrollOffset":80,"TriggerNameLowerCase":"scroll","ParentComponentWithTrigger":null,"BackgroundColor":"rgb(44, 53, 62)","BackgroundGradientStartingColor":"","BackgroundGradientEndingColor":"","BackgroundGradientDirection":0,"BackgroundGradientDegrees":0.0000000,"BackgroundImageFileName":"","BackgroundImagePositionXUseKeyword":true,"BackgroundImagePositionXKeyword":0,"BackgroundImagePositionX":{"Value":0.0,"Unit":0},"BackgroundImagePositionYUseKeyword":true,"BackgroundImagePositionYKeyword":0,"BackgroundImagePositionY":{"Value":0.0,"Unit":0},"BackgroundImageRepeat":0,"BorderStyle":0,"BorderWidth":0,"BorderColor":"","BorderSides":15,"BorderRadiusTopLeft":{"Value":null,"Unit":1},"BorderRadiusTopRight":{"Value":null,"Unit":1},"BorderRadiusBottomRight":{"Value":null,"Unit":1},"BorderRadiusBottomLeft":{"Value":null,"Unit":1},"MarginTop":{"Value":null,"Unit":0},"MarginRight":{"Value":null,"Unit":0},"MarginBottom":{"Value":null,"Unit":0},"MarginLeft":{"Value":null,"Unit":0},"PaddingTop":{"Value":null,"Unit":0},"PaddingRight":{"Value":null,"Unit":0},"PaddingBottom":{"Value":null,"Unit":0},"PaddingLeft":{"Value":null,"Unit":0},"MiscellaneousStyles":"box-shadow: 0px 3px 6px #00000029;","RecordStatus":0}] 